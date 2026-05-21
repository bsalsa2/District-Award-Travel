"""
High-performance Kafka producer for award availability streaming.
Designed for mechanical sympathy with batching and compression.
"""

from confluent_kafka import Producer
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from platform.src.config import config
from platform.src.schemas import AwardAvailability

# Configure logging for high-throughput environments
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kafka_producer.log')
    ]
)
logger = logging.getLogger(__name__)

class KafkaAwardProducer:
    """
    High-performance Kafka producer optimized for award availability streaming.
    Uses batching, compression, and async delivery for maximum throughput.
    """

    def __init__(self):
        """Initialize producer with optimized configuration."""
        self.producer_config = {
            'bootstrap.servers': config.kafka.bootstrap_servers,
            'message.max.bytes': config.kafka.max_message_size,
            'linger.ms': config.kafka.linger_ms,
            'batch.size': config.kafka.batch_size,
            'compression.type': config.kafka.compression_type,
            'acks': config.kafka.acks,
            'enable.idempotence': True,
            'queue.buffering.max.messages': 100000,
            'queue.buffering.max.kbytes': 102400,  # 100MB
            'delivery.report.only.error': False,
            'socket.blocking.max.ms': 100,
        }

        self.producer = Producer(self.producer_config)

        # Schema registry for Avro/JSON schema validation
        self.schema_registry_config = {
            'url': 'http://localhost:8081'  # Would be configurable
        }
        self.schema_registry = SchemaRegistryClient(self.schema_registry_config)

        # JSON serializer
        self.json_serializer = JSONSerializer(
            schema_str=self._get_schema(),
            schema_registry=self.schema_registry
        )

        # Metrics
        self.messages_sent = 0
        self.messages_failed = 0
        self.last_flush_time = datetime.utcnow()

    def _get_schema(self) -> str:
        """Return JSON schema for award availability."""
        return json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "award_type": {"type": "string", "enum": ["flight", "hotel", "car", "cruise", "other"]},
                "status": {"type": "string", "enum": ["available", "limited", "unavailable", "pending"]},
                "source": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "flight_segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "departure_airport": {"type": "object"},
                            "arrival_airport": {"type": "object"},
                            "departure_time": {"type": "string", "format": "date-time"},
                            "arrival_time": {"type": "string", "format": "date-time"},
                            "flight_number": {"type": "string"},
                            "operating_airline": {"type": "object"},
                            "marketing_airline": {"type": "object"},
                            "cabin_class": {"type": "string"},
                            "flight_duration_minutes": {"type": "integer"}
                        }
                    }
                },
                "points_required": {"type": "integer"},
                "currency": {"type": "string"}
            },
            "required": ["id", "award_type", "status", "source"]
        })

    def _delivery_report(self, err, msg):
        """Callback for message delivery reports."""
        if err is not None:
            self.messages_failed += 1
            logger.error(f"Message delivery failed: {err}")
        else:
            self.messages_sent += 1
            if self.messages_sent % 1000 == 0:
                logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def produce_message(self, topic: str, message: AwardAvailability) -> bool:
        """
        Produce a message to Kafka with async delivery report.

        Args:
            topic: Kafka topic name
            message: AwardAvailability message to send

        Returns:
            bool: True if message was successfully queued, False otherwise
        """
        try:
            # Serialize the message
            serialized_data = self.json_serializer(
                message.model_dump(),
                SerializationContext(
                    topic=topic,
                    field=MessageField.VALUE
                )
            )

            # Produce the message with callback
            self.producer.produce(
                topic=topic,
                value=serialized_data,
                callback=self._delivery_report
            )

            # Periodically flush to ensure messages are sent
            if (datetime.utcnow() - self.last_flush_time).total_seconds() > 5:
                self.producer.flush(timeout=1)
                self.last_flush_time = datetime.utcnow()

            return True
        except Exception as e:
            self.messages_failed += 1
            logger.error(f"Failed to produce message: {e}")
            return False

    def flush(self):
        """Force flush all buffered messages."""
        self.producer.flush(timeout=10)

    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics."""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "queue_size": self.producer.queue().size(),
            "timestamp": datetime.utcnow().isoformat()
        }

    def close(self):
        """Cleanup producer resources."""
        self.flush()
        self.producer.close()

# Global producer instance
producer = KafkaAwardProducer()

def get_producer() -> KafkaAwardProducer:
    """Get the global producer instance."""
    return producer
