#!/usr/bin/env python3
"""
Real-time Flight Data Ingestion Service
Handles live flight inventory, award availability, and dynamic pricing feeds
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Any

import aioredis
import asyncpg
from confluent_kafka import Consumer, KafkaException, TopicPartition
from prometheus_client import Counter, Gauge, start_http_server
from pythonjsonlogger import jsonlogger

# Configure logging
log_handler = logging.StreamHandler()
log_handler.setFormatter(jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
))
logger = logging.getLogger('flight_ingestion')
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# Metrics
MESSAGES_PROCESSED = Counter(
    'flight_ingestion_messages_processed_total',
    'Total number of messages processed'
)
MESSAGES_FAILED = Counter(
    'flight_ingestion_messages_failed_total',
    'Total number of messages failed to process'
)
PROCESSING_TIME = Gauge(
    'flight_ingestion_processing_time_seconds',
    'Time spent processing messages'
)
KAFKA_LAG = Gauge(
    'flight_ingestion_kafka_lag',
    'Current Kafka consumer lag'
)

class FlightIngestionService:
    def __init__(self):
        self.config = self._load_config()
        self.kafka_consumer = None
        self.redis_client = None
        self.db_pool = None
        self.running = False
        self.shutdown_event = asyncio.Event()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        return {
            'kafka_brokers': os.getenv('KAFKA_BROKERS', 'kafka:9092'),
            'kafka_group_id': os.getenv('KAFKA_GROUP_ID', 'flight-ingestion-group'),
            'kafka_topics': os.getenv('KAFKA_TOPICS', 'flight-inventory,award-availability,pricing-updates').split(','),
            'redis_host': os.getenv('REDIS_HOST', 'redis'),
            'redis_port': int(os.getenv('REDIS_PORT', '6379')),
            'redis_db': int(os.getenv('REDIS_DB', '0')),
            'postgres_host': os.getenv('POSTGRES_HOST', 'postgres'),
            'postgres_port': int(os.getenv('POSTGRES_PORT', '5432')),
            'postgres_user': os.getenv('POSTGRES_USER', 'awardtravel'),
            'postgres_password': os.getenv('POSTGRES_PASSWORD', 'changeme'),
            'postgres_db': os.getenv('POSTGRES_DB', 'flight_intelligence'),
            'log_level': os.getenv('LOG_LEVEL', 'info'),
            'metrics_port': int(os.getenv('METRICS_PORT', '9091')),
        }

    async def initialize(self):
        """Initialize all connections and resources"""
        try:
            # Initialize Kafka consumer
            self.kafka_consumer = Consumer({
                'bootstrap.servers': self.config['kafka_brokers'],
                'group.id': self.config['kafka_group_id'],
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': False,
                'queued.max.messages.kbytes': 1024,
                'fetch.max.bytes': 52428800,
                'max.partition.fetch.bytes': 10485760,
            })

            # Subscribe to topics
            self.kafka_consumer.subscribe(self.config['kafka_topics'])

            # Initialize Redis client
            self.redis_client = await aioredis.from_url(
                f'redis://{self.config["redis_host"]}:{self.config["redis_port"]}/{self.config["redis_db"]}',
                decode_responses=True
            )

            # Initialize PostgreSQL connection pool
            self.db_pool = await asyncpg.create_pool(
                host=self.config['postgres_host'],
                port=self.config['postgres_port'],
                user=self.config['postgres_user'],
                password=self.config['postgres_password'],
                database=self.config['postgres_db'],
                min_size=5,
                max_size=20,
                max_inactive_connection_lifetime=300,
            )

            # Start metrics server
            start_http_server(self.config['metrics_port'])
            logger.info('Flight ingestion service initialized successfully')

        except Exception as e:
            logger.error(f'Failed to initialize service: {str(e)}')
            raise

    async def process_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """Process a single message based on its topic"""
        start_time = datetime.now(timezone.utc)

        try:
            if topic == 'flight-inventory':
                await self._process_flight_inventory(message)
            elif topic == 'award-availability':
                await self._process_award_availability(message)
            elif topic == 'pricing-updates':
                await self._process_pricing_update(message)
            else:
                logger.warning(f'Unknown topic: {topic}')

            MESSAGES_PROCESSED.inc()
            PROCESSING_TIME.set((datetime.now(timezone.utc) - start_time).total_seconds())
            return True

        except Exception as e:
            logger.error(f'Failed to process message: {str(e)}', extra={
                'topic': topic,
                'message': message,
                'error': str(e)
            })
            MESSAGES_FAILED.inc()
            return False

    async def _process_flight_inventory(self, data: Dict[str, Any]):
        """Process flight inventory data"""
        flight_number = data.get('flight_number')
        departure = data.get('departure')
        arrival = data.get('arrival')
        aircraft = data.get('aircraft')
        seats_available = data.get('seats_available', {})

        # Store in Redis with TTL
        await self.redis_client.hset(
            f'flight:inventory:{flight_number}',
            mapping={
                'departure': json.dumps(departure),
                'arrival': json.dumps(arrival),
                'aircraft': aircraft,
                'seats_available': json.dumps(seats_available),
                'last_updated': datetime.utcnow().isoformat()
            }
        )
        await self.redis_client.expire(f'flight:inventory:{flight_number}', 3600)  # 1 hour TTL

        # Store in PostgreSQL
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO flight_inventory (
                    flight_number, departure, arrival, aircraft, seats_available,
                    last_updated, source
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (flight_number) DO UPDATE SET
                    departure = EXCLUDED.departure,
                    arrival = EXCLUDED.arrival,
                    aircraft = EXCLUDED.aircraft,
                    seats_available = EXCLUDED.seats_available,
                    last_updated = EXCLUDED.last_updated,
                    source = EXCLUDED.source
            ''', flight_number, json.dumps(departure), json.dumps(arrival),
               aircraft, json.dumps(seats_available),
               datetime.utcnow(), data.get('source', 'unknown'))

    async def _process_award_availability(self, data: Dict[str, Any]):
        """Process award availability data"""
        award_id = data.get('award_id')
        flight_segments = data.get('flight_segments', [])
        available_seats = data.get('available_seats', 0)
        currency = data.get('currency', 'USD')
        price = data.get('price', 0)
        expires_at = data.get('expires_at')

        # Store in Redis with TTL
        await self.redis_client.hset(
            f'award:{award_id}',
            mapping={
                'flight_segments': json.dumps(flight_segments),
                'available_seats': str(available_seats),
                'price': str(price),
                'currency': currency,
                'expires_at': expires_at,
                'last_updated': datetime.utcnow().isoformat()
            }
        )
        await self.redis_client.expire(f'award:{award_id}', 1800)  # 30 minute TTL

        # Store in PostgreSQL
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO award_availability (
                    award_id, flight_segments, available_seats, price, currency,
                    expires_at, last_updated, source
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (award_id) DO UPDATE SET
                    flight_segments = EXCLUDED.flight_segments,
                    available_seats = EXCLUDED.available_seats,
                    price = EXCLUDED.price,
                    currency = EXCLUDED.currency,
                    expires_at = EXCLUDED.expires_at,
                    last_updated = EXCLUDED.last_updated,
                    source = EXCLUDED.source
            ''', award_id, json.dumps(flight_segments), available_seats,
               price, currency, expires_at, datetime.utcnow(),
               data.get('source', 'unknown'))

    async def _process_pricing_update(self, data: Dict[str, Any]):
        """Process dynamic pricing updates"""
        route_key = data.get('route_key')
        pricing_tier = data.get('pricing_tier')
        price = data.get('price')
        currency = data.get('currency')
        expires_at = data.get('expires_at')

        # Store in Redis with TTL
        await self.redis_client.hset(
            f'pricing:{route_key}',
            mapping={
                'pricing_tier': pricing_tier,
                'price': str(price),
                'currency': currency,
                'expires_at': expires_at,
                'last_updated': datetime.utcnow().isoformat()
            }
        )
        await self.redis_client.expire(f'pricing:{route_key}', 900)  # 15 minute TTL

        # Store in PostgreSQL
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO pricing_updates (
                    route_key, pricing_tier, price, currency, expires_at,
                    last_updated, source
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (route_key) DO UPDATE SET
                    pricing_tier = EXCLUDED.pricing_tier,
                    price = EXCLUDED.price,
                    currency = EXCLUDED.currency,
                    expires_at = EXCLUDED.expires_at,
                    last_updated = EXCLUDED.last_updated,
                    source = EXCLUDED.source
            ''', route_key, pricing_tier, price, currency, expires_at,
               datetime.utcnow(), data.get('source', 'unknown'))

    async def consume_messages(self):
        """Main message consumption loop"""
        logger.info('Starting message consumption loop')
        self.running = True

        while not self.shutdown_event.is_set():
            try:
                msg = self.kafka_consumer.poll(timeout=1.0)

                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        # End of partition event
                        logger.info(f'Reached end of partition {msg.topic()} [{msg.partition()}]')
                    else:
                        logger.error(f'Kafka error: {msg.error()}')
                    continue

                # Process message
                topic = msg.topic()
                try:
                    data = json.loads(msg.value().decode('utf-8'))
                    success = await self.process_message(topic, data)

                    if success:
                        self.kafka_consumer.commit(msg)
                        KAFKA_LAG.set(msg.offset())

                except json.JSONDecodeError as e:
                    logger.error(f'Failed to decode message: {str(e)}', extra={
                        'topic': topic,
                        'raw_message': msg.value().decode('utf-8', errors='replace')
                    })
                    MESSAGES_FAILED.inc()

            except Exception as e:
                logger.error(f'Unexpected error in consumption loop: {str(e)}')
                await asyncio.sleep(1)

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info('Starting graceful shutdown')
        self.running = False
        self.shutdown_event.set()

        # Close Kafka consumer
        if self.kafka_consumer:
            self.kafka_consumer.close()

        # Close database connections
        if self.db_pool:
            await self.db_pool.close()

        # Close Redis connections
        if self.redis_client:
            await self.redis_client.close()

        logger.info('Graceful shutdown completed')

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    asyncio.create_task(ingestion_service.shutdown())

async def main():
    """Main entry point"""
    global ingestion_service

    ingestion_service = FlightIngestionService()

    try:
        await ingestion_service.initialize()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        await ingestion_service.consume_messages()

    except Exception as e:
        logger.error(f'Service failed: {str(e)}')
        await ingestion_service.shutdown()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
