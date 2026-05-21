"""
High-performance Kafka consumer for award availability processing.
Designed for mechanical sympathy with prefetching and batch processing.
"""

from confluent_kafka import Consumer, KafkaException
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from platform.src.config import config
from platform.src.schemas import AwardAvailability
from platform.src.models import FlightAward, HotelAward, CarAward, AwardMetadata
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy
from cassandra.query import BatchStatement, SimpleStatement
from cassandra import ConsistencyLevel
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kafka_consumer.log')
    ]
)
logger = logging.getLogger(__name__)

class KafkaAwardConsumer:
    """
    High-performance Kafka consumer optimized for award availability processing.
    Uses batching, async I/O, and efficient Cassandra writes.
    """

    def __init__(self):
        """Initialize consumer with optimized configuration."""
        self.consumer_config = {
            'bootstrap.servers': config.kafka.bootstrap_servers,
            'group.id': config.kafka.group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
            'heartbeat.interval.ms': 3000,
            'session.timeout.ms': 10000,
            'max.poll.interval.ms': 300000,
            'fetch.max.bytes': 52428800,  # 50MB
            'max.partition.fetch.bytes': 1048576,  # 1MB
            'fetch.max.wait.ms': 100,
            'default.topic.config': {
                'auto.offset.reset': 'earliest'
            }
        }

        self.consumer = Consumer(self.consumer_config)

        # Schema registry for message deserialization
        self.json_deserializer = JSONDeserializer(
            schema_str=self._get_schema()
        )

        # Cassandra connection pool
        self.cassandra_cluster = Cluster(
            contact_points=config.cassandra.hosts,
            port=config.cassandra.port,
            protocol_version=4,
            load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='datacenter1'),
            connect_timeout=5,
            idle_heartbeat_interval=30,
            idle_heartbeat_timeout=60
        )
        self.session = self.cassandra_cluster.connect()
        self.session.row_factory = dict_factory

        # Prepare statements for batch inserts
        self._prepare_statements()

        # Metrics
        self.messages_processed = 0
        self.messages_failed = 0
        self.last_commit_time = datetime.utcnow()

        # Subscribed topics
        self.topics = [
            f"{config.kafka.topic_prefix}_flights",
            f"{config.kafka.topic_prefix}_hotels",
            f"{config.kafka.topic_prefix}_cars"
        ]

    def _get_schema(self) -> str:
        """Return JSON schema for deserialization."""
        return json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "award_type": {"type": "string"},
                "status": {"type": "string"},
                "source": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "flight_segments": {"type": "array"},
                "points_required": {"type": "integer"},
                "currency": {"type": "string"}
            }
        })

    def _prepare_statements(self):
        """Prepare Cassandra statements for efficient batching."""
        # Flight award insert
        self.flight_insert = self.session.prepare("""
            INSERT INTO award_availability.flight_awards (
                departure_date, origin, destination, award_id,
                flight_number, cabin_class, airline_iata, status,
                points_required, cash_required, total_price, currency,
                departure_time, arrival_time, flight_duration,
                operating_airline, marketing_airline, source, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)
        self.flight_insert.consistency_level = ConsistencyLevel.LOCAL_QUORUM

        # Hotel award insert
        self.hotel_insert = self.session.prepare("""
            INSERT INTO award_availability.hotel_awards (
                check_in_date, property_id, award_id, nights,
                room_type, status, points_required, cash_required,
                total_price, currency, source, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)
        self.hotel_insert.consistency_level = ConsistencyLevel.LOCAL_QUORUM

        # Car award insert
        self.car_insert = self.session.prepare("""
            INSERT INTO award_availability.car_awards (
                pickup_date, pickup_location, award_id, vehicle_id,
                status, points_required, cash_required, total_price,
                currency, source, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)
        self.car_insert.consistency_level = ConsistencyLevel.LOCAL_QUORUM

        # Metadata update
        self.metadata_update = self.session.prepare("""
            UPDATE award_availability.award_metadata
            SET last_updated = ?, records_processed = records_processed + 1
            WHERE source = ?
        """)
        self.metadata_update.consistency_level = ConsistencyLevel.LOCAL_QUORUM

    def _deserialize_message(self, msg) -> Optional[AwardAvailability]:
        """Deserialize Kafka message to AwardAvailability object."""
        try:
            data = self.json_deserializer(
                msg.value(),
                SerializationContext(
                    topic=msg.topic(),
                    field=MessageField.VALUE
                )
            )
            return AwardAvailability(**data)
        except Exception as e:
            logger.error(f"Failed to deserialize message: {e}")
            self.messages_failed += 1
            return None

    def _process_flight_award(self, award: AwardAvailability) -> bool:
        """Process flight award and insert into Cassandra."""
        try:
            if not award.flight_segments or len(award.flight_segments) == 0:
                logger.warning(f"Flight award {award.id} has no segments")
                return False

            segment = award.flight_segments[0]

            # Create batch statement
            batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_QUORUM)

            # Insert flight award
            batch.add(self.flight_insert, (
                award.departure_date.date() if award.departure_date else None,
                award.origin.iata_code if award.origin else None,
                award.destination.iata_code if award.destination else None,
                award.id,
                segment.flight_number,
                segment.cabin_class.value,
                segment.operating_airline.iata_code,
                award.status.value,
                award.points_required,
                award.cash_required,
                award.total_price,
                award.currency,
                segment.departure_time,
                segment.arrival_time,
                segment.flight_duration_minutes,
                segment.operating_airline.name,
                segment.marketing_airline.name,
                award.source,
                award.metadata or {}
            ))

            # Execute batch
            self.session.execute(batch)
            return True
        except Exception as e:
            logger.error(f"Failed to process flight award {award.id}: {e}")
            self.messages_failed += 1
            return False

    def _process_hotel_award(self, award: AwardAvailability) -> bool:
        """Process hotel award and insert into Cassandra."""
        try:
            batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_QUORUM)

            batch.add(self.hotel_insert, (
                award.check_in_date.date() if award.check_in_date else None,
                award.property_id,
                award.id,
                award.nights,
                award.room_type,
                award.status.value,
                award.points_required,
                award.cash_required,
                award.total_price,
                award.currency,
                award.source,
                award.metadata or {}
            ))

            self.session.execute(batch)
            return True
        except Exception as e:
            logger.error(f"Failed to process hotel award {award.id}: {e}")
            self.messages_failed += 1
            return False

    def _process_car_award(self, award: AwardAvailability) -> bool:
        """Process car award and insert into Cassandra."""
        try:
            batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_QUORUM)

            batch.add(self.car_insert, (
                award.pickup_time.date() if award.pickup_time else None,
                award.pickup_location.iata_code if award.pickup_location else None,
                award.id,
                award.vehicle_id,
                award.status.value,
                award.points_required,
                award.cash_required,
                award.total_price,
                award.currency,
                award.source,
                award.metadata or {}
            ))

            self.session.execute(batch)
            return True
        except Exception as e:
            logger.error(f"Failed to process car award {award.id}: {e}")
            self.messages_failed += 1
            return False

    def _update_metadata(self, source: str):
        """Update metadata counters."""
        try:
            self.session.execute(self.metadata_update, (
                datetime.utcnow(),
                source
            ))
        except Exception as e:
            logger.error(f"Failed to update metadata for {source}: {e}")

    def process_messages(self, batch_size: int = 1000):
        """
        Process messages from Kafka in batches.

        Args:
            batch_size: Number of messages to process in each batch
        """
        self.consumer.subscribe(self.topics)

        logger.info(f"Starting consumer for topics: {self.topics}")

        try:
            while True:
                # Poll for messages with timeout
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    # No message received within timeout period
                    continue
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        # End of partition event
                        logger.debug(f"Reached end of partition {msg.topic()} [{msg.partition()}]")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue

                # Process the message
                award = self._deserialize_message(msg)
                if award:
                    success = False
                    if award.award_type == "flight":
                        success = self._process_flight_award(award)
                    elif award.award_type == "hotel":
                        success = self._process_hotel_award(award)
                    elif award.award_type == "car":
                        success = self._process_car_award(award)

                    if success:
                        self.messages_processed += 1
                        self._update_metadata(award.source)

                # Periodically commit offsets
                if self.messages_processed % batch_size == 0:
                    self.consumer.commit(asynchronous=True)
                    self.last_commit_time = datetime.utcnow()
                    logger.info(f"Processed {self.messages_processed} messages")

        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            # Cleanup
            self.consumer.close()
            self.session.shutdown()
            self.cassandra_cluster.shutdown()

    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics."""
        return {
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "timestamp": datetime.utcnow().isoformat()
        }

def dict_factory(colnames, rows):
    """Convert Cassandra rows to dictionaries."""
    return [dict(zip(colnames, row)) for row in rows]

# Global consumer instance
consumer = KafkaAwardConsumer()

def get_consumer() -> KafkaAwardConsumer:
    """Get the global consumer instance."""
    return consumer
