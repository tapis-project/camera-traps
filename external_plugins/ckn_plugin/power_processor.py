"""
Power Processor - Reads power summary from file and streams to Kafka.

This module can be used standalone or imported by ckn_plugin.
The main ckn_plugin.py has this logic inlined, but this module
is kept for compatibility and testing.
"""

import json
import os
import time
import logging


def build_connect_envelope(payload, field_types, required_fields=None):
    """Wrap a flat dict in a Kafka Connect JSON schema envelope (schema+payload).

    Mirrors the helper in ckn_plugin.py - the JDBC sink connectors run with
    value.converter.schemas.enable=true, so bare JSON is silently dropped.
    """
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


class PowerProcessor:
    """
    Processes the power events and sends events to the CKN Broker.
    """
    def __init__(self, power_summary_file, kafka_producer, topic, experiment_id, max_attempts=5, timeout=10):
        self.power_summary_file = power_summary_file
        self.kafka_producer = kafka_producer
        self.topic = topic
        self.experiment_id = experiment_id
        self.max_attempts = int(max_attempts) if max_attempts is not None else 5
        self.timeout = int(timeout) if timeout is not None else 10

    def get_power_summary(self):
        """
        Reads the power summary from the power summary file.
        Returns a flattened event dictionary.
        """
        with open(self.power_summary_file, 'r') as file:
            data = json.load(file)

        # Extract the plugin power summary report
        power_summary = data.get("plugin power summary report", [])

        # Initialize a dictionary for the flattened event
        flattened_event = {}

        # Initialize total CPU and GPU consumption
        total_cpu_consumption = 0.0
        total_gpu_consumption = 0.0

        # Iterate over each plugin's data and add it to the flattened event
        for plugin_data in power_summary:
            plugin_name = plugin_data.get("plugin", "unknown")

            # Add plugin's CPU and GPU consumption to the flattened event
            cpu_consumption = plugin_data.get("cpu_power_consumption", 0.0)
            gpu_consumption = plugin_data.get("gpu_power_consumption", 0.0)

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
        """
        attempt = 0
        while attempt < self.max_attempts:
            if os.path.exists(self.power_summary_file):
                logging.info("Reading the power summary file...")

                try:
                    # Read the power summary
                    power_summary = self.get_power_summary()
                    envelope = build_connect_envelope(
                        power_summary, build_power_field_types(power_summary), {"experiment_id"}
                    )
                    power_summary_json = json.dumps(envelope)

                    # Send the event to Kafka
                    if self.kafka_producer:
                        self.kafka_producer.produce(self.topic, key=self.experiment_id, value=power_summary_json)
                        self.kafka_producer.flush()
                        logging.info("Power summary streamed to Kafka.")
                    else:
                        logging.info("Kafka producer not available; read power summary but did not stream.")
                        logging.debug(f"Power summary payload: {power_summary_json}")
                    return
                except Exception as e:
                    logging.error(f"Error processing power summary: {e}")
                    return

            # Increment the attempt count and wait before trying again
            attempt += 1
            logging.info(f"Power summary file not found, attempt {attempt}/{self.max_attempts}")
            time.sleep(self.timeout)

        logging.warning("No power summary file found after all attempts.")
