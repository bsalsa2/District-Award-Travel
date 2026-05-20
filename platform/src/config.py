import os
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class KafkaConfig:
    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic_airline_data: str = os.getenv("KAFKA_TOPIC_AIRLINE_DATA", "airline-data-raw")
    topic_fare_changes: str = os.getenv("KAFKA_TOPIC_FARE_CHANGES", "fare-changes-raw")
    topic_user_searches: str = os.getenv("KAFKA_TOPIC_USER_SEARCHES", "user-searches-raw")
    topic_pricing_updates: str = os.getenv("KAFKA_TOPIC_PRICING_UPDATES", "pricing-updates")
    group_id: str = os.getenv("KAFKA_GROUP_ID", "award-pricing-group")
    auto_offset_reset: str = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
    enable_auto_commit: bool = os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "false").lower() == "true"

@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    db: int = int(os.getenv("REDIS_DB", "0"))
    max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
    stream_key: str = os.getenv("REDIS_STREAM_KEY", "award_pricing_updates")

@dataclass
class MLConfig:
    model_path: str = os.getenv("ML_MODEL_PATH", "/models/award_pricing_model.onnx")
    inference_batch_size: int = int(os.getenv("ML_BATCH_SIZE", "1000"))
    gpu_device: str = os.getenv("GPU_DEVICE", "cuda:0")
    warmup_iterations: int = int(os.getenv("ML_WARMUP_ITERATIONS", "100"))
    max_latency_ms: int = int(os.getenv("ML_MAX_LATENCY_MS", "100"))

@dataclass
class PipelineConfig:
    max_events_per_second: int = int(os.getenv("MAX_EVENTS_PER_SECOND", "10000000"))
    processing_timeout_ms: int = int(os.getenv("PROCESSING_TIMEOUT_MS", "500"))
    checkpoint_interval: int = int(os.getenv("CHECKPOINT_INTERVAL", "60"))
    enable_gpu_direct: bool = os.getenv("ENABLE_GPU_DIRECT", "false").lower() == "true"
    enable_profiling: bool = os.getenv("ENABLE_PROFILING", "false").lower() == "true"

class Config:
    kafka = KafkaConfig()
    redis = RedisConfig()
    ml = MLConfig()
    pipeline = PipelineConfig()

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "kafka": {
                "bootstrap_servers": cls.kafka.bootstrap_servers,
                "topics": {
                    "airline_data": cls.kafka.topic_airline_data,
                    "fare_changes": cls.kafka.topic_fare_changes,
                    "user_searches": cls.kafka.topic_user_searches,
                    "pricing_updates": cls.kafka.topic_pricing_updates,
                }
            },
            "redis": {
                "host": cls.redis.host,
                "port": cls.redis.port,
                "db": cls.redis.db
            },
            "ml": {
                "model_path": cls.ml.model_path,
                "gpu_device": cls.ml.gpu_device,
                "batch_size": cls.ml.inference_batch_size
            },
            "pipeline": {
                "max_events_per_second": cls.pipeline.max_events_per_second,
                "processing_timeout_ms": cls.pipeline.processing_timeout_ms
            }
        }
