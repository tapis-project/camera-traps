import os
import zmq
import logging
import json
import yaml
import sys
import time
import threading
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from ctevents.ctevents import socket_message_to_typed_event, send_terminate_plugin_fb_event
from ctevents import ImageStoredEvent, ImageDeletedEvent, ImageScoredEvent, ImageReceivedEvent, PluginTerminatingEvent

# Try to import watchdog for file watching (optional)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Try to import Kafka producer, handle gracefully if not available
try:
    from confluent_kafka import Producer, KafkaError
    from confluent_kafka.admin import AdminClient
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger = logging.getLogger("CKN Plugin")
    logger.warning("confluent-kafka not available. Kafka streaming will be disabled.")

# Try to import power processor, handle gracefully if not available
try:
    from power_processor import PowerProcessor
    POWER_PROCESSOR_AVAILABLE = True
except ImportError:
    # In many deployments, only this file is copied into the container (see Dockerfile),
    # so a separate power_processor module is not available. Provide an internal fallback
    # so power summary processing still works when ENABLE_POWER_MONITORING is enabled.
    class PowerProcessor:
        def __init__(
            self,
            summary_file,
            kafka_producer,
            kafka_topic,
            experiment_id,
            max_tries=5,
            timeout=10,
        ):
            self.summary_file = summary_file
            self.kafka_producer = kafka_producer
            self.kafka_topic = kafka_topic
            self.experiment_id = experiment_id
            self.max_tries = int(max_tries) if max_tries is not None else 5
            self.timeout = int(timeout) if timeout is not None else 10

        def _wait_for_summary_file(self):
            """
            Wait for the power summary report file to exist and be readable.
            The power monitoring plugin generates this near its shutdown, so the
            CKN plugin may reach shutdown first.
            """
            last_err = None
            for _ in range(max(self.max_tries, 1)):
                try:
                    if self.summary_file and os.path.exists(self.summary_file) and os.path.getsize(self.summary_file) > 0:
                        return True
                except Exception as e:
                    last_err = e
                time.sleep(max(self.timeout, 0))
            if last_err:
                raise last_err
            return False

        def process_summary_events(self):
            """
            Reads the summary JSON and publishes it to Kafka (if available).
            Expected file is typically: /power_logs/power_summary_report.json
            """
            if not self.summary_file:
                raise ValueError("summary_file is empty")

            if not self._wait_for_summary_file():
                raise FileNotFoundError(f"Power summary file not found or empty at {self.summary_file}")

            with open(self.summary_file, "r") as f:
                summary = json.load(f)

            payload = {
                "experiment_id": self.experiment_id,
                "device_id": os.environ.get("CAMERA_TRAPS_DEVICE_ID", ""),
                "user_id": os.environ.get("USER_ID", ""),
                "power_summary_file": self.summary_file,
                "power_summary": summary,
            }

            # If Kafka isn't available (or producer failed to initialize), we still
            # consider "processing" successful once the file is readable.
            if not self.kafka_producer:
                logger.info("Kafka producer not initialized; read power summary successfully but will not publish to Kafka.")
                logger.debug(f"Power summary payload: {json.dumps(payload)}")
                return

            # Publish summary to Kafka
            value = json.dumps(payload)
            self.kafka_producer.produce(self.kafka_topic, key=self.experiment_id, value=value)
            self.kafka_producer.flush()

    POWER_PROCESSOR_AVAILABLE = True

log_level = os.environ.get("CKN_LOG_LEVEL", "INFO")
logger = logging.getLogger("CKN Plugin")

# Log watchdog availability after logger is initialized
if not WATCHDOG_AVAILABLE:
    logger.warning("watchdog not available. File watching mode will be disabled.")
if log_level == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif log_level == "INFO":
    logger.setLevel(logging.INFO)
elif log_level == "WARN":
    logger.setLevel(logging.WARN)
elif log_level == "ERROR":
    logger.setLevel(logging.ERROR)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Number of images generated by the entire application (i.e., by the image generating plugin)
total_images_generated = 0

# Number of images processed by this CKN plugin 
total_images_processed = 0

# Whether this program has received the PluginTerminating event from the image generating plugin
received_terminating_signal = False

# list of image UUIDs for which the CKN plugin is not able to initially retrieve the basic information 
# from the uuid_image_mapping file (written by image generating plugin)
uuids_with_errors = []

# Set of UUIDs that have been sent to Kafka to avoid duplicates
processed_uuids = set()

# Kafka producer instance
kafka_producer = None

# Running experiment-level metrics
experiment_metrics = {
    "total_images": 0,
    "total_predictions": 0,
    "total_ground_truth_objects": 0,
    "true_positives": 0,
    "false_positives": 0,
    "false_negatives": 0,
    "precision": 0.0,
    "recall": 0.0,
    "f1_score": 0.0,
    "mean_iou": None,
    "map_50": None,
    "map_50_95": None,
    # Internal accumulators for IoU/mAP
    "sum_iou": 0.0,
    "num_iou_pairs": 0,
    "gt_boxes_count": 0,
}

# For mAP: keep per-threshold prediction lists of (score, is_tp)
map_thresholds = [round(t, 2) for t in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]]
map_data = {t: [] for t in map_thresholds}

PORT = int(os.environ.get('CKN_PLUGIN_PORT', 6011))
OUTPUT_DIR = os.environ.get('TRAPS_CKN_OUTPUT_PATH', "/output/")
MODEL_ID = os.environ.get("MODEL_ID")

# Option to watch file instead of/in addition to ZMQ events
# If ORACLE_CSV_PATH is set, watch that file (for compatibility with oracle_plugin)
WATCH_ORACLE_FILE = os.environ.get('ORACLE_CSV_PATH', '')
ENABLE_FILE_WATCHER = bool(WATCH_ORACLE_FILE and WATCH_ORACLE_FILE != output_file and WATCHDOG_AVAILABLE)

# Set of UUIDs processed from file watching (to avoid duplicates)
file_processed_uuids = set()
file_watcher_stop = False

# Kafka configuration
KAFKA_BROKER = os.environ.get('CKN_KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = os.environ.get('CKN_KAFKA_TOPIC', 'oracle-events')
DEVICE_ID = os.environ.get('CAMERA_TRAPS_DEVICE_ID', '')
EXPERIMENT_ID = os.environ.get('EXPERIMENT_ID', '')
USER_ID = os.environ.get('USER_ID', '')

# Power monitoring configuration
ENABLE_POWER_MONITORING = os.environ.get('ENABLE_POWER_MONITORING', 'false')
POWER_SUMMARY_FILE = os.environ.get('POWER_SUMMARY_FILE', '')
POWER_SUMMARY_TOPIC = os.environ.get('POWER_SUMMARY_TOPIC', 'cameratraps-power-summary')

# This is the ground truth file; this file is written by the image generating plugin and only read
# by the CKN plugin (not written to)
uuid_image_mapping_path = os.path.join(OUTPUT_DIR, "uuid_image_mapping.json")

# Image detecting plugin
VIDEO_INFO_FILE = os.environ.get('TRAPS_VIDEO_INFO_PATH', '')

# This is the file the CKN plugin actually writes
output_file = os.path.join(OUTPUT_DIR, "image_mapping_final.json")

SOCKET_TIMEOUT = 2000


def get_socket():
    context = zmq.Context()
    return get_plugin_socket(context, PORT)


def test_ckn_broker_connection(configuration, timeout=10, num_tries=5):
    """
    Checks if the CKN broker is up and running.
    """
    if not KAFKA_AVAILABLE:
        return False
    for i in range(num_tries):
        try:
            admin_client = AdminClient(configuration)
            # Access the topics, if not successful wait
            topics = admin_client.list_topics(timeout=timeout)
            return True
        except Exception as e:
            logger.info(f"CKN broker not available yet: {e}. Retrying in 5 seconds...")
            time.sleep(5)
    logger.info(f"Could not connect to the CKN broker...")
    return False


def initialize_kafka_producer():
    """
    Initialize Kafka producer with SSL configuration.
    """
    global kafka_producer
    if not KAFKA_AVAILABLE:
        logger.warning("Kafka not available, skipping producer initialization")
        return False
    
    kafka_conf = {'bootstrap.servers': KAFKA_BROKER, 'log_level': 0, 'security.protocol': 'SSL'}
    
    logger.info(f"Connecting to the CKN broker at {KAFKA_BROKER}")
    
    # Wait for CKN broker to be available
    ckn_broker_available = test_ckn_broker_connection(kafka_conf)
    
    if not ckn_broker_available:
        logger.warning(f"Shutting down CKN Plugin Kafka producer due to broker not being available")
        return False
    
    # Successful connection to CKN broker
    logger.info(f"Successfully connected to the CKN broker at {KAFKA_BROKER}")
    
    # Initialize the Kafka producer
    kafka_producer = Producer(**kafka_conf)
    return True


def _compute_iou(box_a, box_b):
    """
    Compute IoU between two boxes in [x, y, w, h] format with normalized coordinates.
    """
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0.0, aw) * max(0.0, ah)
    area_b = max(0.0, bw) * max(0.0, bh)
    union = area_a + area_b - inter_area
    return (inter_area / union) if union > 0 else 0.0


def _greedy_match(preds, gts, iou_threshold):
    """
    Greedy 1-1 matching between predictions and ground truths by IoU threshold.
    Returns list of (pred_idx, gt_idx, iou) for matches.
    """
    matches = []
    used_preds = set()
    used_gts = set()
    # Precompute IoU matrix
    iou_matrix = []
    for pi, p in enumerate(preds):
        pbox = p.get("bounding_box")
        if not pbox:
            continue  # Skip predictions without bounding boxes
        prow = []
        for gi, g in enumerate(gts):
            gbox = g.get("bounding_box")
            if not gbox:
                continue  # Skip ground truths without bounding boxes
            iou = _compute_iou(pbox, gbox)
            prow.append((gi, iou))
        iou_matrix.append((pi, prow))
    # Iterate by descending IoU candidates
    candidates = []
    for pi, prow in iou_matrix:
        for gi, iou in prow:
            candidates.append((iou, pi, gi))
    candidates.sort(reverse=True)
    for iou, pi, gi in candidates:
        if iou < iou_threshold:
            break
        if pi in used_preds or gi in used_gts:
            continue
        matches.append((pi, gi, iou))
        used_preds.add(pi)
        used_gts.add(gi)
    return matches, used_preds, used_gts


def _update_map_structures(predictions, gt_boxes):
    """
    Update per-threshold AP structures using label-aware matches.
    """
    global map_data, map_thresholds
    for thr in map_thresholds:
        matches, used_preds, used_gts = _greedy_match(predictions, gt_boxes, thr)
        # Label-aware: only count as TP if labels match
        matched_gt_by_pred = {pi: gi for pi, gi, _ in matches}
        for pi, pred in enumerate(predictions):
            score = float(pred.get("probability", 0.0))
            if pi in matched_gt_by_pred:
                gi = matched_gt_by_pred[pi]
                if str(pred.get("label")) == str(gt_boxes[gi].get("label")):
                    map_data[thr].append((score, True))
                else:
                    map_data[thr].append((score, False))
            else:
                map_data[thr].append((score, False))


def _compute_ap(preds_list, num_gt):
    """
    Compute AP given list of (score, is_tp) and total GT count.
    Uses standard 11-point interpolation-like precision envelope integration.
    """
    if num_gt <= 0 or not preds_list:
        return 0.0
    # Sort by score desc
    preds_sorted = sorted(preds_list, key=lambda x: x[0], reverse=True)
    tp_cum = 0
    fp_cum = 0
    precisions = []
    recalls = []
    for score, is_tp in preds_sorted:
        if is_tp:
            tp_cum += 1
        else:
            fp_cum += 1
        precision = tp_cum / max(tp_cum + fp_cum, 1)
        recall = tp_cum / num_gt
        precisions.append(precision)
        recalls.append(recall)
    # Precision envelope
    for i in range(len(precisions) - 2, -1, -1):
        if precisions[i] < precisions[i + 1]:
            precisions[i] = precisions[i + 1]
    # Integrate AP over recall from 0 to 1 based on observed points
    ap = 0.0
    prev_recall = 0.0
    for p, r in zip(precisions, recalls):
        if r > prev_recall:
            ap += p * (r - prev_recall)
            prev_recall = r
    return ap


def _update_experiment_metrics(ground_truth_label, scores_list, ground_truth_boxes=None):
    """
    Update running experiment metrics based on a single image's ground truth label and predictions.
    If ground-truth bounding boxes are provided as a list of {label, bounding_box}, compute IoU and mAP.
    """
    global experiment_metrics, map_data, map_thresholds
    
    # Normalize inputs
    gt = None if ground_truth_label is None else str(ground_truth_label)
    has_gt_object = gt is not None and gt.lower() not in ["empty", "unknown"]

    predictions = scores_list if isinstance(scores_list, list) else []
    num_predictions = len(predictions)
    predicted_labels = [str(p.get("label")) for p in predictions if p and p.get("label") is not None]

    # If GT boxes exist, use detection-based accounting; else use classification fallback
    detection_mode = isinstance(ground_truth_boxes, list) and len(ground_truth_boxes) > 0
    increment_true_positive = 0
    increment_false_negative = 0
    increment_false_positive = 0
    if detection_mode:
        # Ensure GT boxes have label and bounding_box
        gt_boxes = [g for g in ground_truth_boxes if g and g.get("bounding_box") is not None]
        experiment_metrics["gt_boxes_count"] += len(gt_boxes)
        # Update mAP structures
        _update_map_structures(predictions, gt_boxes)
        # Compute matches at IoU 0.5 for TP/FP/FN and IoU accumulation
        matches, used_preds, used_gts = _greedy_match(predictions, gt_boxes, 0.5)
        # Label-aware TP
        tp_count = 0
        sum_iou_img = 0.0
        for pi, gi, iou in matches:
            if str(predictions[pi].get("label")) == str(gt_boxes[gi].get("label")):
                tp_count += 1
                sum_iou_img += iou
        fp_count = max(num_predictions - len(used_preds), 0)
        fn_count = max(len(gt_boxes) - len(used_gts), 0)
        increment_true_positive = tp_count
        increment_false_positive = fp_count
        increment_false_negative = fn_count
        # Update IoU accumulators
        if tp_count > 0:
            experiment_metrics["sum_iou"] += sum_iou_img
            experiment_metrics["num_iou_pairs"] += tp_count
    else:
        # Classification-based TP/FP/FN (1 GT object at most per image in current data)
        has_correct_prediction = has_gt_object and any(lbl == gt for lbl in predicted_labels)
        increment_true_positive = 1 if has_correct_prediction else 0
        increment_false_negative = 1 if has_gt_object and not has_correct_prediction else 0
        increment_false_positive = max(num_predictions - (1 if has_correct_prediction else 0), 0)

    # Update totals
    experiment_metrics["total_images"] += 1
    experiment_metrics["total_predictions"] += num_predictions
    if detection_mode:
        experiment_metrics["total_ground_truth_objects"] += len(ground_truth_boxes)
    else:
        experiment_metrics["total_ground_truth_objects"] += 1 if has_gt_object else 0
    experiment_metrics["true_positives"] += increment_true_positive
    experiment_metrics["false_negatives"] += increment_false_negative
    experiment_metrics["false_positives"] += increment_false_positive

    # Derived metrics
    tp = float(experiment_metrics["true_positives"]) 
    fp = float(experiment_metrics["false_positives"]) 
    fn = float(experiment_metrics["false_negatives"]) 
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    experiment_metrics["precision"] = precision
    experiment_metrics["recall"] = recall
    experiment_metrics["f1_score"] = f1
    # Mean IoU
    if experiment_metrics["num_iou_pairs"] > 0:
        experiment_metrics["mean_iou"] = experiment_metrics["sum_iou"] / experiment_metrics["num_iou_pairs"]
    # mAP@0.5 and mAP@0.5:0.95 using accumulated predictions
    if experiment_metrics["gt_boxes_count"] > 0:
        # AP at 0.5
        ap50 = _compute_ap(map_data[0.5], experiment_metrics["gt_boxes_count"]) if 0.5 in map_data else 0.0
        # Mean AP across thresholds
        ap_values = []
        for t in map_thresholds:
            ap_values.append(_compute_ap(map_data[t], experiment_metrics["gt_boxes_count"]))
        map_50_95 = sum(ap_values) / len(ap_values) if ap_values else 0.0
        experiment_metrics["map_50"] = ap50
        experiment_metrics["map_50_95"] = map_50_95


def stream_event_to_kafka(event_data):
    """
    Stream event to Kafka broker.
    """
    global kafka_producer, processed_uuids
    
    if not kafka_producer:
        return
    
    uuid = event_data.get('UUID')
    if not uuid or uuid in processed_uuids:
        return
    
    try:
        # Add metadata to event
        event_data['device_id'] = DEVICE_ID
        event_data['experiment_id'] = EXPERIMENT_ID
        event_data['user_id'] = USER_ID
        
        row_json = json.dumps(event_data)
        
        # Send the event
        kafka_producer.produce(KAFKA_TOPIC, key=EXPERIMENT_ID, value=row_json)
        kafka_producer.flush()
        
        # Add to processed set only if produce succeeds
        processed_uuids.add(uuid)
        logger.info(f"Streamed event to CKN broker for UUID: {uuid}")
        
    except BufferError as e:
        logger.error(f"Buffer error streaming to CKN broker: {e}")
    except Exception as e:
        logger.error(f"CKN broker error streaming event: {e}")


def compute_total_images_generated():
    """
    Reads the uuid_image_mapping file to determine how many images were generated by this execution.
    """
    if os.path.exists(uuid_image_mapping_path):
        with open(uuid_image_mapping_path, 'r') as f:
            try:
                d = json.load(f)
            except Exception as e:
                logger.error(f"Error parsing uuid_image_mapping file when trying to compute total images generated; details: {e}")
                return -1 
        # the number of images generated is just the total number of keys in the file
        return len(d.keys())
    elif os.path.exists(VIDEO_INFO_FILE):
        with open(VIDEO_INFO_FILE, 'r') as f:
            video_info = yaml.safe_load(f)
            return video_info.get('num_images')
    else:
        logger.error(f"Valid image mapping file not found.")
        return -1 


def compute_total_images_processed():
    """
    Reads the image_mapping_final file to determine how many images have been processed.
    """
    total = 0
    with open(output_file, 'r') as f:
        try:
            d = json.load(f)
        except Exception as e:
            logger.error(f"Error parsing image_mapping_final file when trying to compute total images processed; details: {e}")
            return total
    # read through the entries and count all images which have a final decision
    for _, v in d.items():
        if v.get("image_decision"):
            total += 1
    return total


def update_json(uuid, updated_data):
    """
    This function updates the existing image_mapping_final dictionary for a given image with id, `uuid`, 
    and a dictionary, `updated_data`, with additional fields to write for the image. 
    """
    global total_images_processed, total_images_generated
    
    # load current dictionary from the image_mapping_final file 
    existing_image_mapping_final = {}
    try:
        with open(output_file, 'r') as f:
            try:
                existing_image_mapping_final = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decoding error for {output_file}; details: {e}")        
    except FileNotFoundError:
        # for the first image, the file has not been created yet and FileNotFound is expected
        if not total_images_processed == 0:
            logger.error(f"File not found: {output_file}")

    # if the uuid is not yet in the image_mapping_final file, go to the uuid_image_mapping file, written
    # by the image generating plugin, to get basic information. The uuid should always be in this file 
    # since the image generating plugin writes the uuid to that file before sending a new image event, 
    if uuid not in existing_image_mapping_final:
        logger.info(f"Fetching {uuid} from {uuid_image_mapping_path}")
        uuid_image_mapping = {}
        try:
            with open(uuid_image_mapping_path, 'r') as file:
                try:
                    uuid_image_mapping = json.load(file)
                    # If we were able to load the uuid_image_mapping file, try to recover any UUID that 
                    # was previously on the error list 
                    if uuids_with_errors:
                        for failed_uuid in uuids_with_errors:
                            if failed_uuid in existing_image_mapping_final:
                                existing_image_mapping_final[failed_uuid].update(uuid_image_mapping[failed_uuid])
                            else:
                               existing_image_mapping_final[failed_uuid] = uuid_image_mapping[failed_uuid]
                            uuids_with_errors.remove(failed_uuid)
                
                # it is possible the image generating plugin was writing to the file at the same time and,
                # at the moment we read the file, the contents of the file are not valid JSON.
                except json.JSONDecodeError as e:                    
                    logger.error(f"JSON loading Error loading uuid_image_mapping.json file while processing uuid: {uuid}; details: {e}")
                    # we were not able to read the uuid_image_mapping.json file, so add this uuid to the error list
                    uuids_with_errors.append(uuid)
        except FileNotFoundError:
            # the uuid_image_mapping file should always at least exist
            logger.error(f"File {uuid_image_mapping_path} not found. This is unexpected and represents a bug.")

        # use the uuid_image_mapping file to get the base info for this image, if possible, and otherwise,
        # create a new dictionary with just the UUID field.
        existing_image_mapping_final[uuid] = uuid_image_mapping.get(uuid, {"UUID": uuid})

    # iterate through the update_data parameter and add them to the existing data
    for key, value in updated_data.items():
        existing_image_mapping_final[uuid][key] = value    
    
    # write the updates mapping back to the file
    with open(output_file, "w") as f: 
        json.dump(existing_image_mapping_final, f, indent=2)
    
    # If image_decision is present, stream to Kafka
    if "image_decision" in updated_data:
        # Read the complete entry to stream
        event_entry = existing_image_mapping_final.get(uuid, {})
        if event_entry:
            # Update experiment metrics before building event payload
            ground_truth = event_entry.get("ground_truth")
            scores = event_entry.get("score", [])
            ground_truth_boxes = event_entry.get("ground_truth_boxes") or event_entry.get("ground_truth_bboxes")
            _update_experiment_metrics(ground_truth, scores, ground_truth_boxes)
            
            # Build event payload from the JSON entry
            event_payload = build_event_payload(event_entry)
            if event_payload:
                stream_event_to_kafka(event_payload)


def build_event_payload(event_entry):
    """
    Build event payload from JSON entry for Kafka streaming.
    No metrics computation - just forward raw data.
    """
    uuid = event_entry.get("UUID")
    if not uuid:
        return None
    
    # Extract all relevant fields
    image_count = event_entry.get("image_count")
    image_name = event_entry.get("image_name")
    ground_truth = event_entry.get("ground_truth")
    ground_truth_boxes = event_entry.get("ground_truth_boxes") or event_entry.get("ground_truth_bboxes")
    image_receiving_timestamp = event_entry.get("image_receiving_timestamp")
    image_scoring_timestamp = event_entry.get("image_scoring_timestamp")
    image_store_delete_time = event_entry.get("image_store_delete_time") or event_entry.get("image_delete_time")
    image_decision = event_entry.get("image_decision")
    model_id = event_entry.get("model_id") or MODEL_ID
    
    # Extract scores
    scores = event_entry.get("score", [])
    flattened_scores = json.dumps(scores) if scores else None
    
    # Extract highest probability label and probability
    label = None
    probability = 0.0
    if scores:
        highest_score = max(scores, key=lambda x: x.get("probability", 0.0))
        label = highest_score.get("label")
        probability = highest_score.get("probability", 0.0)
    
    # Build event payload
    event = {
        "image_count": image_count,
        "UUID": uuid,
        "image_name": image_name,
        "ground_truth": ground_truth,
        "image_receiving_timestamp": image_receiving_timestamp,
        "image_scoring_timestamp": image_scoring_timestamp,
        "model_id": model_id,
        "label": label,
        "probability": probability,
        "image_store_delete_time": image_store_delete_time,
        "image_decision": image_decision,
        "flattened_scores": flattened_scores,
        # Running totals for the experiment at the moment of this event
        "total_images": experiment_metrics["total_images"],
        "total_predictions": experiment_metrics["total_predictions"],
        "total_ground_truth_objects": experiment_metrics["total_ground_truth_objects"],
        "true_positives": experiment_metrics["true_positives"],
        "false_positives": experiment_metrics["false_positives"],
        "false_negatives": experiment_metrics["false_negatives"],
        "precision": experiment_metrics["precision"],
        "recall": experiment_metrics["recall"],
        "f1_score": experiment_metrics["f1_score"],
        "mean_iou": experiment_metrics["mean_iou"],
        "map_50": experiment_metrics["map_50"],
        "map_50_95": experiment_metrics["map_50_95"],
    }
    
    # Add ground truth boxes if available
    if ground_truth_boxes:
        event["ground_truth_boxes"] = ground_truth_boxes
    
    return event


def add_terminating_function_json(special_uuid):
    """
    This function writes a 'special' UUID that may be used for compatibility.
    It first checks one last time for images in the uuids_with_errors file and tries to retrieve 
    them 
    """
    # read the existing output data 
    with open(output_file, "r") as f: 
        existing_image_mapping_final = json.load(f)
    
    # check if we still have UUIDs with errors
    if uuids_with_errors:
        uuid_image_mapping = {}
        # try to read the mapping file and make the corrections
        try:
            with open(uuid_image_mapping_path, 'r') as file:
                try:
                    uuid_image_mapping = json.load(file)
                except Exception as e:
                    logger.error(f"Could not load JSON from uuid_image_mapping file at the very end; details: {e}")
        except Exception as e:
            logger.error(f"Got exception trying to open the uuid_image_mapping file at the very end; details: {e}")
        if uuid_image_mapping:
            for failed_uuid in uuids_with_errors:
                # we should always have SOME data for all failed uuids, so this 
                if not existing_image_mapping_final.get(failed_uuid):
                    existing_image_mapping_final[failed_uuid] = {}
                    logger.error(f"In final processing and existing_image_mapping_final had no data for uuid {failed_uuid}")
                # extend the existing mapping data with the uuid data
                existing_image_mapping_final[failed_uuid].update(uuid_image_mapping[failed_uuid])
                uuids_with_errors.remove(failed_uuid)
                logger.info(f"Updated final mapping at the end for failed UUID {failed_uuid}")

    # add the special UUID to the mapping file; it gets an empty dict since it does not correspond to a 
    # real image
    existing_image_mapping_final[special_uuid] = {}
    
    # write the complete mapping file:
    with open(output_file, "w") as f: 
        json.dump(existing_image_mapping_final, f, indent=2)


class OracleFileEventHandler(FileSystemEventHandler):
    """
    Event handler for watching the oracle output file (when oracle_plugin runs separately).
    """
    def __init__(self, file_path):
        self.file_path = file_path
        self.last_size = 0

    def on_modified(self, event):
        """When the file is modified, process new entries."""
        if event.src_path == self.file_path:
            logger.debug(f"File {self.file_path} modified, processing events...")
            process_file_events(self.file_path)


def process_file_events(file_path):
    """
    Read events from the oracle output file and stream to Kafka.
    This replicates the behavior of ckn_daemon.py.
    """
    global file_processed_uuids, file_watcher_stop
    
    if not os.path.exists(file_path):
        return
    
    try:
        # Load the JSON data from the file
        while True:
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    break
            except json.JSONDecodeError:
                logger.debug("File not complete. Waiting for the file to be completely written")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return

        EXPERIMENT_END_SIGNAL = os.getenv('EXPERIMENT_END_SIGNAL', '6e153711-9823-4ee6-b608-58e2e801db51')
        shutdown_signal = False
        
        # Process each entry in the JSON data
        for key, value in data.items():
            # Shutdown signal received from oracle
            if key == EXPERIMENT_END_SIGNAL:
                shutdown_signal = True
                continue

            # Only process entries with image_decision
            if "image_decision" not in value:
                continue

            uuid = value.get("UUID")
            if not uuid or uuid in file_processed_uuids:
                continue

            # Update experiment metrics
            ground_truth = value.get("ground_truth")
            scores = value.get("score", [])
            ground_truth_boxes = value.get("ground_truth_boxes") or value.get("ground_truth_bboxes")
            _update_experiment_metrics(ground_truth, scores, ground_truth_boxes)

            # Build and stream event
            event_payload = build_event_payload(value)
            if event_payload:
                stream_event_to_kafka(event_payload)
                file_processed_uuids.add(uuid)

        # Handle shutdown signal
        if shutdown_signal:
            logger.info("Shutdown signal from Oracle file received...")
            global file_watcher_stop
            file_watcher_stop = True

    except Exception as e:
        logger.error(f"Error processing file events: {e}")


def start_file_watcher(file_path):
    """
    Start a file watcher thread to monitor the oracle output file.
    """
    if not WATCHDOG_AVAILABLE:
        logger.warning("watchdog not available, cannot start file watcher")
        return None
    
    observer = Observer()
    event_handler = OracleFileEventHandler(file_path)
    observer.schedule(event_handler, path=os.path.dirname(file_path) or '.', recursive=False)
    observer.start()
    logger.info(f"Started file watcher for: {file_path}")
    return observer


def process_power_summary():
    """
    Process power summary at shutdown if enabled.
    """
    if ENABLE_POWER_MONITORING.lower() != 'false' and POWER_PROCESSOR_AVAILABLE and POWER_SUMMARY_FILE:
        try:
            power_processor = PowerProcessor(
                POWER_SUMMARY_FILE, 
                kafka_producer, 
                POWER_SUMMARY_TOPIC, 
                EXPERIMENT_ID, 
                5,  # max_tries
                10  # timeout
            )
            power_processor.process_summary_events()
            logger.info("Power summary processed.")
        except Exception as e:
            logger.warning(f"Could not process power summary: {e}")
    elif ENABLE_POWER_MONITORING.lower() != 'false':
        logger.warning("Power monitoring enabled but power_processor module not available or POWER_SUMMARY_FILE not set")


def main():
    """
    Main loop for CKN plugin; this function waits for new messages on the event socket and processes accordingly:
      1. Image received, scored, stored, deleted: update the image_mapping_final and stream to Kafka
      2. Plugin terminating (from image generating): Compute total images needed to be processed.
    
    If ORACLE_CSV_PATH is set, also watches that file for events (compatibility mode with oracle_plugin).
    """
    # Initialize Kafka producer
    initialize_kafka_producer()
    
    # Start file watcher if oracle_plugin is running separately
    file_observer = None
    if ENABLE_FILE_WATCHER:
        # Wait for the file to exist
        while not os.path.exists(WATCH_ORACLE_FILE):
            logger.info(f"Waiting for {WATCH_ORACLE_FILE} to exist...")
            time.sleep(1)
        file_observer = start_file_watcher(WATCH_ORACLE_FILE)
        # Also process any existing events in the file
        process_file_events(WATCH_ORACLE_FILE)
    
    done = False
    while not done:
        socket = get_socket()
        try:
            message = get_next_msg(socket)
        except zmq.error.Again:
            logger.debug(f"Got a zmq.error.Again; i.e., waited {SOCKET_TIMEOUT} ms without getting a message")
            continue
        except Exception as e:
            logger.debug(f"Got exception from get_next_msg; type(e): {type(e)}; e: {e}")
            done = True 
            logger.info("CKN plugin stopping due to timeout limit...")
            continue
        if not message:
            logger.info("No message found in get_next_msg")

        logger.info("Got a message from the event socket - CKN plugin check")
        event = socket_message_to_typed_event(message)

        if isinstance(event, ImageReceivedEvent):
            uuid = event.ImageUuid().decode('utf-8')
            timestamp = event.EventCreateTs().decode('utf-8').strip("'")
            logger.info(f"Image received {uuid} {timestamp}")
            update_json(uuid, {"image_receiving_timestamp": timestamp})

        elif isinstance(event, ImageScoredEvent):
            uuid = event.ImageUuid().decode('utf-8')
            scores = []
            for i in range(event.ScoresLength()):
                label = event.Scores(i).Label().decode('utf-8')
                prob = event.Scores(i).Probability()
                scores.append({"label": label, "probability": prob})
            timestamp = event.EventCreateTs().decode('utf-8')
            logger.info(f"Inside scoring {uuid} {scores} {timestamp}")
            update_json(uuid, {"image_scoring_timestamp": timestamp, "score": scores})

        elif isinstance(event, ImageStoredEvent):
            uuid = event.ImageUuid().decode('utf-8')
            timestamp = event.EventCreateTs().decode('utf-8')
            destination = event.Destination().decode('utf-8')
            logger.info(f"Image stored {uuid} {timestamp} {destination}")
            update_json(uuid, {"image_store_delete_time": timestamp, "image_decision": destination})

        elif isinstance(event, ImageDeletedEvent):
            uuid = event.ImageUuid().decode('utf-8')
            timestamp = event.EventCreateTs().decode('utf-8')
            logger.info(f"Image deleted {uuid} {timestamp}")
            update_json(uuid, {"image_delete_time": timestamp, "image_decision": "Deleted"})

        elif isinstance(event, PluginTerminatingEvent):
            plugin_name = event.PluginName().decode('utf-8')
            if plugin_name in ['ext_image_gen_plugin','ext_image_detecting_plugin']:
                logger.info(f"Received Terminating signal from {plugin_name}")
                # at this point, we can compute the total images generated and to be processed from the
                # length of the uuid_image_mapping
                global received_terminating_signal
                received_terminating_signal = True
                total_images_generated = compute_total_images_generated()
                logger.info(f"Total images generated: {total_images_generated}")         
        
        # Once we have received the terminating signal, we compute total_images_processed 
        if received_terminating_signal:
            total_images_processed = compute_total_images_processed()
            logger.info(f"CKN plugin has processed: {total_images_processed} out of {total_images_generated}")       
            if total_images_generated < 0:
                total_images_generated = compute_total_images_generated()
       
        if received_terminating_signal \
        and total_images_generated > 0 \
        and total_images_generated == total_images_processed:
            logger.info("Initiating shut down for all other plugins...")
            add_terminating_function_json("6e153711-9823-4ee6-b608-58e2e801db51")
            send_terminate_plugin_fb_event(socket, "*", "6e153711-9823-4ee6-b608-58e2e801db51")
            logger.info("Sent PluginTerminate * event")
            time.sleep(1)
            
            # Process power summary if enabled
            process_power_summary()
            
            # Stop file watcher if running
            if file_observer:
                file_observer.stop()
                file_observer.join()
            
            send_quit_command(socket)
            logger.info("Sent quit command.")
            sys.exit()
        else:
            logger.info(event)
        
        # Check if file watcher should stop
        if file_watcher_stop:
            logger.info("File watcher stop signal received...")
            if file_observer:
                file_observer.stop()
                file_observer.join()
            process_power_summary()
            send_quit_command(socket)
            logger.info("Sent quit command.")
            sys.exit()


if __name__ == '__main__':
    logger.info("CKN plugin starting...")
    main()
    logger.info("CKN plugin exiting...")

