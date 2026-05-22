import os

class Settings:
    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
    AIRLINE_API_KEY = os.environ.get("AIRLINE_API_KEY", "")
    AIRLINE_API_SECRET = os.environ.get("AIRLINE_API_SECRET", "")

settings = Settings()
