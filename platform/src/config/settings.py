import os
from pydantic import BaseSettings, RedisDsn, PostgresDsn
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: PostgresDsn = "postgresql://district:awardtravel@localhost:5432/district_award"
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"

    # AI Model
    AI_MODEL_PATH: str = "/models/award_predictor_v2"
    TENSORRT_ENGINE: str = "/models/award_predictor_v2.engine"
    NEMO_MODEL: str = "nvidia/award-availability-v1"

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "District Award Travel - Predictive Engine"

    # Cache
    PREDICTION_CACHE_TTL: int = 900  # 15 minutes
    ROUTE_CACHE_TTL: int = 3600  # 1 hour

    # Scraping
    SCRAPE_INTERVAL: int = 3600  # 1 hour
    MAX_CONCURRENT_SCRAPERS: int = 10

    # Predictive Holds
    MAX_PREDICTIVE_HOLDS: int = 1000
    HOLD_EXPIRY_MINUTES: int = 1440  # 24 hours

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
