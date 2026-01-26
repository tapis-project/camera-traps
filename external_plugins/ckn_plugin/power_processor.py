import os
import json
import time
import logging

logger = logging.getLogger("PowerProcessor")


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
        CKN daemon may reach shutdown first.
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
        logger.info(f"Power summary published to Kafka topic: {self.kafka_topic}")
