import os
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str = os.getenv("POSTGRES_HOST", "postgres")
    port: int = 5432
    db_name: str = os.getenv("POSTGRES_DB", "award_predictions")
    user: str = os.getenv("POSTGRES_USER", "award_user")
    password: str = os.getenv("POSTGRES_PASSWORD", "award_password")
    ssl_mode: str = "disable"

    @property
    def connection_string(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"

@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "redis")
    port: int = 6379
    db: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"

@dataclass
class ModelConfig:
    s3_bucket: str = os.getenv("MODEL_S3_BUCKET", "award-travel-models")
    local_path: str = "/app/models"
    max_memory_mb: int = 4096
    gpu_memory_fraction: float = 0.8

@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    prediction_port: int = 8000
    ab_testing_port: int = 8002
    health_check_interval: int = 30

@dataclass
class RLConfig:
    learning_rate: float = 0.001
    discount_factor: float = 0.99
    exploration_rate: float = 0.1
    batch_size: int = 64
    target_update_freq: int = 100
    memory_size: int = 10000
    train_interval: int = 10

@dataclass
class AWSAirlineAPIConfig:
    base_url: str = "https://api.airlinex.com/v1"
    timeout: int = 30
    max_retries: int = 3
    api_key: str = os.getenv("AIRLINE_API_KEY", "default_key")

@dataclass
class FlightPredictionConfig:
    max_routes: int = 10000
    cache_ttl: int = 3600  # 1 hour
    prediction_horizon_days: int = 365
    min_confidence: float = 0.7
    seasonal_adjustment_window: int = 30

@dataclass
class MonitoringConfig:
    prometheus_port: int = 9090
    grafana_port: int = 3000
    log_level: str = "INFO"
    metrics_enabled: bool = True

@dataclass
class Config:
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    model: ModelConfig = ModelConfig()
    api: APIConfig = APIConfig()
    rl: RLConfig = RLConfig()
    airline_api: AWSAirlineAPIConfig = AWSAirlineAPIConfig()
    flight_prediction: FlightPredictionConfig = FlightPredictionConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    environment: str = os.getenv("ENVIRONMENT", "development")

    def __post_init__(self):
        if self.environment == "production":
            self.monitoring.log_level = "WARNING"
            self.monitoring.metrics_enabled = True

config = Config()
