"""
Configuration module for the Award Availability Pipeline.
Designed for high-throughput streaming with mechanical sympathy.
"""

import os
from dataclasses import dataclass
from typing import List

@dataclass
class KafkaConfig:
    """Kafka configuration optimized for low-latency streaming."""
    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic_prefix: str = os.getenv("KAFKA_TOPIC_PREFIX", "award_availability")
    group_id: str = os.getenv("KAFKA_GROUP_ID", "award-consumer-group")
    max_message_size: int = int(os.getenv("KAFKA_MAX_MESSAGE_SIZE", "10485760"))  # 10MB
    linger_ms: int = int(os.getenv("KAFKA_LINGER_MS", "5"))  # Wait up to 5ms for batching
    batch_size: int = int(os.getenv("KAFKA_BATCH_SIZE", "16384"))  # 16KB batch size
    compression_type: str = os.getenv("KAFKA_COMPRESSION_TYPE", "snappy")
    acks: str = os.getenv("KAFKA_ACKS", "all")  # Wait for all replicas to acknowledge

@dataclass
class CassandraConfig:
    """Cassandra configuration optimized for high write throughput."""
    hosts: List[str] = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
    port: int = int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace: str = os.getenv("CASSANDRA_KEYSPACE", "award_availability")
    username: str = os.getenv("CASSANDRA_USERNAME", "cassandra")
    password: str = os.getenv("CASSANDRA_PASSWORD", "cassandra")
    consistency_level: str = os.getenv("CASSANDRA_CONSISTENCY", "LOCAL_QUORUM")
    write_timeout: int = int(os.getenv("CASSANDRA_WRITE_TIMEOUT_MS", "2000"))
    read_timeout: int = int(os.getenv("CASSANDRA_READ_TIMEOUT_MS", "5000"))
    connection_pool_size: int = int(os.getenv("CASSANDRA_POOL_SIZE", "50"))

@dataclass
class APIConfig:
    """FastAPI configuration for serving award availability."""
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    workers: int = int(os.getenv("API_WORKERS", "4"))
    cache_ttl: int = int(os.getenv("API_CACHE_TTL_SECONDS", "30"))

@dataclass
class ScraperConfig:
    """Configuration for airline API scrapers."""
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    backoff_factor: float = float(os.getenv("BACKOFF_FACTOR", "1.5"))

@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    kafka: KafkaConfig = KafkaConfig()
    cassandra: CassandraConfig = CassandraConfig()
    api: APIConfig = APIConfig()
    scraper: ScraperConfig = ScraperConfig()
    enable_metrics: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    metrics_port: int = int(os.getenv("METRICS_PORT", "9090"))

# Global configuration instance
config = PipelineConfig()
