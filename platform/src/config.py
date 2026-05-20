import os
from typing import Dict, List
from pydantic import BaseSettings, PostgresDsn

class Settings(BaseSettings):
    # API Keys
    AMERICAN_API_KEY: str = os.getenv("AMERICAN_API_KEY", "")
    DELTA_API_KEY: str = os.getenv("DELTA_API_KEY", "")
    UNITED_API_KEY: str = os.getenv("UNITED_API_KEY", "")
    LUFTHANSA_API_KEY: str = os.getenv("LUFTHANSA_API_KEY", "")
    AIR_CANADA_API_KEY: str = os.getenv("AIR_CANADA_API_KEY", "")
    OPEN_AI_API_KEY: str = os.getenv("OPEN_AI_API_KEY", "")
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")

    # Database
    DATABASE_URL: PostgresDsn = os.getenv(
        "DATABASE_URL", "postgresql://district:travel@localhost:5432/district_award"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # GPU Configuration
    GPU_ENABLED: bool = os.getenv("GPU_ENABLED", "true").lower() == "true"
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")
    INDEX_DIMENSIONS: int = int(os.getenv("INDEX_DIMENSIONS", "1024"))

    # Search Configuration
    MAX_QUERY_LENGTH: int = 512
    TOP_K_RESULTS: int = 100
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.75
    CACHE_TTL: int = 300  # 5 minutes

    # API Configuration
    API_RATE_LIMIT: int = 1000  # requests per minute
    API_TIMEOUT: int = 30  # seconds
    MAX_CONCURRENT_REQUESTS: int = 100

    # Flight Data
    FLIGHT_DATA_DIR: str = os.getenv("FLIGHT_DATA_DIR", "/data/flight_cache")
    MAX_FLIGHT_CACHE_AGE: int = 86400  # 24 hours

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# API Endpoints configuration
AIRLINE_APIS: Dict[str, Dict] = {
    "american": {
        "base_url": "https://api.americanairlines.com",
        "api_key": settings.AMERICAN_API_KEY,
        "endpoints": {
            "search": "/v1/flight-offers",
            "availability": "/v1/availability",
            "pricing": "/v1/pricing"
        }
    },
    "delta": {
        "base_url": "https://api.delta.com",
        "api_key": settings.DELTA_API_KEY,
        "endpoints": {
            "search": "/v1/flight-offers",
            "availability": "/v1/availability",
            "pricing": "/v1/pricing"
        }
    },
    "united": {
        "base_url": "https://api.united.com",
        "api_key": settings.UNITED_API_KEY,
        "endpoints": {
            "search": "/v1/flight-offers",
            "availability": "/v1/availability",
            "pricing": "/v1/pricing"
        }
    },
    "lufthansa": {
        "base_url": "https://api.lufthansa.com",
        "api_key": settings.LUFTHANSA_API_KEY,
        "endpoints": {
            "search": "/v1/flight-offers",
            "availability": "/v1/availability",
            "pricing": "/v1/pricing"
        }
    },
    "air_canada": {
        "base_url": "https://api.aircanada.com",
        "api_key": settings.AIR_CANADA_API_KEY,
        "endpoints": {
            "search": "/v1/flight-offers",
            "availability": "/v1/availability",
            "pricing": "/v1/pricing"
        }
    }
}

# Alliance mappings
ALLIANCE_MAPPINGS: Dict[str, List[str]] = {
    "oneworld": ["american", "qantas", "cathay_pacific", "japan_airlines"],
    "skyteam": ["delta", "air_france", "korean_air", "aeromexico"],
    "star_alliance": ["united", "lufthansa", "air_canada", "singapore_airlines"],
    "skyteam_cargo": ["delta_cargo"],
    "star_alliance_cargo": ["lufthansa_cargo"]
}

# Comfort levels
COMFORT_LEVELS = {
    "economy": 1,
    "premium_economy": 2,
    "business": 3,
    "first": 4
}

# Seat types
SEAT_TYPES = {
    "window": 1,
    "aisle": 2,
    "middle": 3,
    "exit_row": 4,
    "bulkhead": 5
}
