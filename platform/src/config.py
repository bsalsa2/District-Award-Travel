import os
from typing import Optional

class Config:
    # Database configuration
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "district_award_travel")
    POSTGRES_POOL_SIZE: int = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
    POSTGRES_MAX_OVERFLOW: int = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))

    # GPU database configuration
    GPU_DB_HOST: str = os.getenv("GPU_DB_HOST", "localhost")
    GPU_DB_PORT: int = int(os.getenv("GPU_DB_PORT", "5433"))
    GPU_DB_USER: str = os.getenv("GPU_DB_USER", "gpu_user")
    GPU_DB_PASSWORD: str = os.getenv("GPU_DB_PASSWORD", "gpu_password")
    GPU_DB_DB: str = os.getenv("GPU_DB_DB", "award_search_gpu")

    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 5 minutes

    # Application configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # Query optimization
    MAX_QUERY_COMPLEXITY: int = int(os.getenv("MAX_QUERY_COMPLEXITY", "100"))
    QUERY_TIMEOUT: int = int(os.getenv("QUERY_TIMEOUT", "5"))  # seconds

    # Feature flags
    USE_GPU_ACCELERATION: bool = os.getenv("USE_GPU_ACCELERATION", "true").lower() == "true"
    ENABLE_QUERY_CACHE: bool = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"
    ENABLE_QUERY_OPTIMIZER: bool = os.getenv("ENABLE_QUERY_OPTIMIZER", "true").lower() == "true"

config = Config()
