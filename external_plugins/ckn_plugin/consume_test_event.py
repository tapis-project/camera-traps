#!/usr/bin/env python3
"""
Consume events from the oracle-events Kafka topic.
"""

import json
import signal
import sys
from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient

# Kafka configuration
KAFKA_BROKER = "cknbroker.pods.icicleai.tapis.io:443"
KAFKA_TOPIC = "oracle-events"
KAFKA_SECURITY_PROTOCOL = "SSL"
CONSUMER_GROUP = "ckn-test-consumer-group"

# Flag to control graceful shutdown
running = True


def signal_handler(sig, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global running
    print("\nShutting down consumer...")
    running = False


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


def consume_events():
    """Consume events from the Kafka topic."""
    global running
    
    # Base config for testing connection
    base_conf = {
        'bootstrap.servers': KAFKA_BROKER,
        'security.protocol': KAFKA_SECURITY_PROTOCOL,
    }
    
    # Test connection first
    if not test_connection(base_conf):
        print("Aborting: Could not connect to Kafka broker")
        return False
    
    # Consumer config
    consumer_conf = {
        'bootstrap.servers': KAFKA_BROKER,
        'security.protocol': KAFKA_SECURITY_PROTOCOL,
        'group.id': CONSUMER_GROUP,
        'auto.offset.reset': 'earliest',  # Start from beginning if no committed offset
        'enable.auto.commit': True,
        'auto.commit.interval.ms': 5000,
    }
    
    print(f"\nCreating Kafka consumer...")
    print(f"Consumer group: {CONSUMER_GROUP}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Starting from: earliest (will read all available messages)")
    
    consumer = Consumer(**consumer_conf)
    consumer.subscribe([KAFKA_TOPIC])
    
    print(f"\n{'='*60}")
    print(f"Listening for events on topic: {KAFKA_TOPIC}")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*60}\n")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    message_count = 0
    
    try:
        while running:
            # Poll for messages with 1 second timeout
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition, not an error
                    print(f"Reached end of partition {msg.partition()}")
                    continue
                else:
                    raise KafkaException(msg.error())
            
            # Process the message
            message_count += 1
            
            print(f"\n{'='*60}")
            print(f"MESSAGE #{message_count}")
            print(f"{'='*60}")
            print(f"Topic: {msg.topic()}")
            print(f"Partition: {msg.partition()}")
            print(f"Offset: {msg.offset()}")
            print(f"Key: {msg.key().decode('utf-8') if msg.key() else 'None'}")
            print(f"Timestamp: {msg.timestamp()}")
            print(f"{'='*60}")
            
            # Parse and pretty-print the JSON payload
            try:
                value = msg.value().decode('utf-8')
                event = json.loads(value)
                print("Event payload:")
                print(json.dumps(event, indent=2))
            except json.JSONDecodeError:
                print(f"Raw value (not JSON): {msg.value()}")
            except Exception as e:
                print(f"Error decoding message: {e}")
            
            print(f"{'='*60}\n")
            
    except Exception as e:
        print(f"Error consuming messages: {e}")
    finally:
        # Close consumer
        print(f"\nClosing consumer... Total messages received: {message_count}")
        consumer.close()
    
    return True


if __name__ == "__main__":
    consume_events()
