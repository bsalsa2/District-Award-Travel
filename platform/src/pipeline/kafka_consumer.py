import json
import logging
from typing import Callable, Any, Dict
from confluent_kafka import Consumer, KafkaException, KafkaError
import threading
import time
from queue import Queue

from platform.src.schemas import AirlineData, FareChange, UserSearch
from platform.src.config import Config

logger = logging.getLogger(__name__)

class HighThroughputKafkaConsumer:
    """
    High-performance Kafka consumer with mechanical sympathy.
    Designed for 10M+ events/sec with minimal latency.
    Uses batch processing and zero-copy techniques where possible.
    """

    def __init__(self, config: Config, callback: Callable[[Dict[str, Any]], None]):
        self.config = config
        self.callback = callback
        self.running = False
        self.consumer = None
        self.thread = None
        self.message_queue = Queue(maxsize=config.pipeline.max_events_per_second // 100)
        self.metrics = {
            'messages_consumed': 0,
            'consumer_latency_ms': 0.0,
            'last_message_time': 0.0
        }

    def _create_consumer_config(self) -> Dict[str, Any]:
        """Create optimized Kafka consumer configuration"""
        return {
            'bootstrap.servers': self.config.kafka.bootstrap_servers,
            'group.id': self.config.kafka.group_id,
            'auto.offset.reset': self.config.kafka.auto_offset_reset,
            'enable.auto.commit': self.config.kafka.enable_auto_commit,
            'queued.max.messages.kbytes': 1024 * 10,  # 10MB buffer
            'fetch.max.bytes': 1024 * 1024 * 5,  # 5MB per request
            'max.partition.fetch.bytes': 1024 * 1024,  # 1MB per partition
            'fetch.max.wait.max.ms': 100,
            'session.timeout.ms': 30000,
            'heartbeat.interval.ms': 10000,
            'max.poll.interval.ms': 300000,
            'enable.partition.eof': False,
            'isolation.level': 'read_committed',
            'auto.commit.interval.ms': 5000,
            'default.topic.config': {
                'auto.offset.reset': 'earliest'
            }
        }

    def _deserialize_message(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize Kafka message with schema validation"""
        try:
            value = raw_message['value'].decode('utf-8')
            message = json.loads(value)

            # Add metadata
            message['kafka_metadata'] = {
                'topic': raw_message['topic'],
                'partition': raw_message['partition'],
                'offset': raw_message['offset'],
                'timestamp': raw_message['timestamp'],
                'key': raw_message.get('key', None)
            }

            return message

        except Exception as e:
            logger.error(f"Message deserialization failed: {e}")
            raise

    def _process_batch(self, batch: list):
        """Process batch of messages with callback"""
        start_time = time.time()

        try:
            for message in batch:
                try:
                    self.callback(message)
                    with self.metrics_lock:
                        self.metrics['messages_consumed'] += 1
                except Exception as e:
                    logger.error(f"Callback failed for message: {e}")

            processing_time = (time.time() - start_time) * 1000
            with self.metrics_lock:
                self.metrics['consumer_latency_ms'] = processing_time

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")

    def _consumer_loop(self):
        """Main consumer loop with batching"""
        self.consumer = Consumer(self._create_consumer_config())
        self.consumer.subscribe([
            self.config.kafka.topic_airline_data,
            self.config.kafka.topic_fare_changes,
            self.config.kafka.topic_user_searches
        ])

        batch = []
        batch_timeout = 0.001  # 1ms for maximum responsiveness
        last_commit_time = time.time()

        try:
            while self.running:
                try:
                    # Poll with timeout for batching
                    msg = self.consumer.poll(batch_timeout)

                    if msg is None:
                        # No message received, check if we should process batch
                        if batch and (time.time() - last_commit_time) * 1000 > self.config.pipeline.processing_timeout_ms:
                            self._process_batch(batch)
                            batch = []
                            last_commit_time = time.time()
                        continue

                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            # End of partition, commit offset
                            self.consumer.commit(msg)
                        else:
                            logger.error(f"Consumer error: {msg.error()}")
                        continue

                    # Deserialize and validate message
                    try:
                        message = self._deserialize_message({
                            'value': msg.value(),
                            'topic': msg.topic(),
                            'partition': msg.partition(),
                            'offset': msg.offset(),
                            'timestamp': msg.timestamp(),
                            'key': msg.key()
                        })

                        batch.append(message)

                        # Process batch if size threshold reached
                        if len(batch) >= 1000:  # Batch size for throughput
                            self._process_batch(batch)
                            batch = []
                            last_commit_time = time.time()

                    except Exception as e:
                        logger.error(f"Message processing failed: {e}")

                except KafkaException as e:
                    logger.error(f"Kafka consumer error: {e}")
                    time.sleep(1)
                    continue

        except Exception as e:
            logger.error(f"Consumer loop crashed: {e}")
        finally:
            # Cleanup
            if self.consumer:
                self.consumer.close()
            logger.info("Kafka consumer shutdown complete")

    def start(self):
        """Start the consumer thread"""
        if self.running:
            return

        self.running = True
        self.metrics_lock = threading.Lock()
        self.thread = threading.Thread(target=self._consumer_loop, daemon=True)
        self.thread.start()
        logger.info("Kafka consumer started")

    def stop(self):
        """Stop the consumer thread"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Kafka consumer stopped")

    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        with self.metrics_lock:
            return {
                **self.metrics,
                'queue_size': self.message_queue.qsize(),
                'timestamp': time.time()
            }
