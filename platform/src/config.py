import os

class Settings:
    KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "award_travel_data")
    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
    REDIS_DB = int(os.environ.get("REDIS_DB", 0))

settings = Settings()
