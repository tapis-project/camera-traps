#!/usr/bin/env python3
"""
Publish test events to Kafka topics:
- oracle-events: Image processing events
- cameratraps-power-summary: Power consumption summary
"""

import json
import uuid
import sys
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient

# Kafka configuration
KAFKA_BROKER = "cknbroker.pods.icicleai.tapis.io:443"
KAFKA_SECURITY_PROTOCOL = "SSL"

# Topics
ORACLE_EVENTS_TOPIC = "oracle-events"
POWER_SUMMARY_TOPIC = "cameratraps-power-summary"

# The JDBC sink connectors run with value.converter.schemas.enable=true, so
# JsonConverter requires each record to be a {"schema": ..., "payload": ...}
# envelope rather than bare JSON - mirrors the helper in ckn_plugin.py.
EVENT_FIELD_TYPES = {
    "device_id": "string",
    "experiment_id": "string",
    "user_id": "string",
    "model_id": "string",
    "image_count": "int32",
    "UUID": "string",
    "image_name": "string",
    "ground_truth": "string",
    "image_receiving_timestamp": "string",
    "image_scoring_timestamp": "string",
    "image_store_delete_time": "string",
    "label": "string",
    "probability": "double",
    "image_decision": "string",
    "flattened_scores": "string",
    "total_images": "int32",
    "total_predictions": "int32",
    "total_ground_truth_objects": "int32",
    "true_positives": "int32",
    "false_positives": "int32",
    "false_negatives": "int32",
    "precision": "double",
    "recall": "double",
    "f1_score": "double",
    "mean_iou": "double",
    "map_50": "double",
    "map_50_95": "double",
}
EVENT_REQUIRED_FIELDS = {"UUID", "experiment_id", "user_id"}


def build_connect_envelope(payload, field_types, required_fields=None):
    """Wrap a flat dict in a Kafka Connect JSON schema envelope (schema+payload)."""
    required_fields = required_fields or set()
    fields = [
        {"field": name, "type": conn_type, "optional": name not in required_fields}
        for name, conn_type in field_types.items()
    ]
    schema = {"type": "struct", "fields": fields, "optional": False}
    return {"schema": schema, "payload": payload}


def build_power_field_types(flattened_event):
    """Power summary keys are dynamic (per-plugin names), so infer types from the event."""
    return {
        name: "string" if name == "experiment_id" else "double"
        for name in flattened_event
    }

# Generate unique IDs for this run
EXPERIMENT_ID = str(uuid.uuid4())

# Sample event matching the ckn_plugin event structure for Neo4j Kafka Connector
# All fields at top level as expected by the Cypher query
SAMPLE_EVENT = {
    # Identity fields - must be pre-registered in patradb (users/edge_devices/models)
    # for the CKN ingest trigger (fn_ingest_camera_trap_event) to accept the row.
    "device_id": "example_device",
    "experiment_id": EXPERIMENT_ID,
    "user_id": "example_user",
    "model_id": "1",
    
    # Image metadata
    "image_count": 1,
    "UUID": str(uuid.uuid4()),
    "image_name": "/example_images/blank01.jpeg",
    "ground_truth": "empty",
    
    # Timestamps
    "image_receiving_timestamp": "2026-02-01T03:52:29.593154603+00:00",
    "image_scoring_timestamp": "2026-02-01T03:52:42.308346",
    "image_store_delete_time": "2026-02-01T03:52:42.309816675+00:00",
    
    # Prediction result (highest probability label)
    "label": "animal",
    "probability": 0.019999999552965164,
    "image_decision": "Deleted",
    
    # Flattened scores as JSON string
    "flattened_scores": '[{"label": "animal", "probability": 0.019999999552965164}, {"label": "animal", "probability": 0.019999999552965164}, {"label": "person", "probability": 0.019999999552965164}, {"label": "person", "probability": 0.009999999776482582}, {"label": "animal", "probability": 0.009999999776482582}, {"label": "animal", "probability": 0.009999999776482582}, {"label": "person", "probability": 0.009999999776482582}]',
    
    # Running experiment metrics
    "total_images": 1,
    "total_predictions": 7,
    "total_ground_truth_objects": 0,
    "true_positives": 0,
    "false_positives": 7,
    "false_negatives": 0,
    "precision": 0.0,
    "recall": 0.0,
    "f1_score": 0.0,
    "mean_iou": None,
    "map_50": None,
    "map_50_95": None
}

# Power summary event for cameratraps-power-summary topic
# FLATTENED structure as expected by Neo4j Kafka Connector Cypher query
POWER_SUMMARY_EVENT = {
    "experiment_id": EXPERIMENT_ID,
    # Per-plugin power consumption (flattened)
    "image_generating_plugin_cpu_power_consumption": 2.6314074074074068,
    "image_generating_plugin_gpu_power_consumption": 0.07603703703703703,
    "power_monitor_plugin_cpu_power_consumption": 2.5915555555555554,
    "power_monitor_plugin_gpu_power_consumption": 0.07137037037037038,
    "image_scoring_plugin_cpu_power_consumption": 2.5690384615384616,
    "image_scoring_plugin_gpu_power_consumption": 0.08219230769230768,
    # Totals
    "total_cpu_power_consumption": 7.792001433501424,  # sum of all CPU
    "total_gpu_power_consumption": 0.22959971509971508  # sum of all GPU
}

class PowerProcessor:
    """
    Processes the power events and sends events to the CKN Broker.
    """
    def __init__(self, power_summary_file, kafka_producer, topic, experiment_id, max_attempts=5, timeout=10):
        self.power_summary_file = power_summary_file
        self.kafka_producer = kafka_producer
        self.topic = topic
        self.experiment_id = experiment_id
        self.max_attempts = max_attempts
        self.timeout = timeout

    def get_power_summary(self):
        """
        Reads the power summary from the power summary file.
        :return:
        """
        with open(self.power_summary_file, 'r') as file:
            data = json.load(file)

        # Extract the plugin power summary report
        power_summary = data["plugin power summary report"]

        # Initialize a dictionary for the flattened event
        flattened_event = {}

        # Initialize total CPU and GPU consumption
        total_cpu_consumption = 0.0
        total_gpu_consumption = 0.0

        # Iterate over each plugin's data and add it to the flattened event
        for plugin_data in power_summary:
            plugin_name = plugin_data["plugin"]

            # Add plugin's CPU and GPU consumption to the flattened event
            cpu_consumption = plugin_data["cpu_power_consumption"]
            gpu_consumption = plugin_data["gpu_power_consumption"]

            flattened_event[f"{plugin_name}_cpu_power_consumption"] = cpu_consumption
            flattened_event[f"{plugin_name}_gpu_power_consumption"] = gpu_consumption

            # Accumulate total CPU and GPU consumption
            total_cpu_consumption += cpu_consumption
            total_gpu_consumption += gpu_consumption

        # Add total CPU and GPU consumption and experiment ID to the flattened event
        flattened_event["total_cpu_power_consumption"] = total_cpu_consumption
        flattened_event["total_gpu_power_consumption"] = total_gpu_consumption
        flattened_event["experiment_id"] = self.experiment_id

        return flattened_event

    def process_summary_events(self):
        """
        Waits for the summary to be available and processes it.
        :return:
        """
        attempt = 0
        # read the file if it's available. total wait time
        while attempt < self.max_attempts:
            if os.path.exists(self.power_summary_file):
                logging.info("Reading the power summary file...")

                # read the power summary
                power_summary = self.get_power_summary()
                power_summary_json = json.dumps(power_summary)

                # send the event to kafka
                self.kafka_producer.produce(self.topic, key=self.experiment_id, value=power_summary_json)
                self.kafka_producer.flush()
                return
            # Increment the attempt count and wait before trying again
            attempt += 1
            time.sleep(self.timeout)

        logging.info("No power summary file found...")


def delivery_callback(err, msg):
    """Callback for message delivery confirmation."""
    if err:
        print(f"ERROR: Message delivery failed: {err}")
    else:
        print(f"SUCCESS: Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")


def test_connection(kafka_conf):
    """Test connection to Kafka broker."""
    print(f"Testing connection to {KAFKA_BROKER}...")
    try:
        admin_client = AdminClient(kafka_conf)
        topics = admin_client.list_topics(timeout=10)
        print(f"Connected! Available topics: {list(topics.topics.keys())}")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


def publish_event(topic, event, key, envelope):
    """Publish an event to the specified Kafka topic, wrapped in a Connect schema envelope."""
    kafka_conf = {
        'bootstrap.servers': KAFKA_BROKER,
        'security.protocol': KAFKA_SECURITY_PROTOCOL,
    }

    # Test connection first
    if not test_connection(kafka_conf):
        print("Aborting: Could not connect to Kafka broker")
        return False

    # Create producer
    print(f"\nCreating Kafka producer...")
    producer = Producer(**kafka_conf)

    # Serialize event
    event_json = json.dumps(envelope)

    print(f"\n{'='*60}")
    print(f"Publishing event to topic: {topic}")
    print(f"Key: {key}")
    print(f"{'='*60}")
    print(f"Event payload:")
    print(json.dumps(event, indent=2))
    print(f"{'='*60}\n")
    
    # Produce message
    producer.produce(
        topic,
        key=key,
        value=event_json,
        callback=delivery_callback
    )
    
    # Wait for delivery
    print("Waiting for delivery confirmation...")
    producer.flush(timeout=30)
    
    print("\nDone!")
    return True


def publish_oracle_event():
    """Publish sample oracle event to oracle-events topic."""
    print("\n" + "="*60)
    print("PUBLISHING ORACLE EVENT")
    print("="*60)
    envelope = build_connect_envelope(SAMPLE_EVENT, EVENT_FIELD_TYPES, EVENT_REQUIRED_FIELDS)
    return publish_event(ORACLE_EVENTS_TOPIC, SAMPLE_EVENT, EXPERIMENT_ID, envelope)


def publish_power_summary():
    """Publish power summary event to cameratraps-power-summary topic."""
    print("\n" + "="*60)
    print("PUBLISHING POWER SUMMARY EVENT")
    print("="*60)
    envelope = build_connect_envelope(
        POWER_SUMMARY_EVENT, build_power_field_types(POWER_SUMMARY_EVENT), {"experiment_id"}
    )
    return publish_event(POWER_SUMMARY_TOPIC, POWER_SUMMARY_EVENT, EXPERIMENT_ID, envelope)


def print_usage():
    """Print usage instructions."""
    print("""
Usage: python3 publish_test_event.py [option]

Options:
  oracle    - Publish oracle event to 'oracle-events' topic
  power     - Publish power summary to 'cameratraps-power-summary' topic
  both      - Publish both events (default)
  help      - Show this help message

Examples:
  python3 publish_test_event.py oracle
  python3 publish_test_event.py power
  python3 publish_test_event.py both
""")


if __name__ == "__main__":
    option = sys.argv[1] if len(sys.argv) > 1 else "both"
    
    if option == "help" or option == "-h" or option == "--help":
        print_usage()
    elif option == "oracle":
        publish_oracle_event()
    elif option == "power":
        publish_power_summary()
    elif option == "both":
        publish_oracle_event()
        publish_power_summary()
    else:
        print(f"Unknown option: {option}")
        print_usage()
        sys.exit(1)
