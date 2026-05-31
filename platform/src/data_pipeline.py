import asyncio
from aiokafka import AIOKafkaConsumer
from platform.src.config import settings
from platform.src.data_processor import DataProcessor
from platform.src.redis_client import RedisClient

class DataPipeline:
    def __init__(self):
        self.kafka_consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id="award_travel_group",
            auto_offset_reset="earliest",
        )
        self.data_processor = DataProcessor()
        self.redis_client = RedisClient()

    async def ingest_data(self):
        await self.kafka_consumer.start()
        try:
            async for message in self.kafka_consumer:
                data = message.value.decode("utf-8")
                processed_data = self.data_processor.process(data)
                await self.redis_client.set(processed_data)
        finally:
            await self.kafka_consumer.stop()

class DataProcessor:
    def process(self, data):
        # Process the data here
        # For example, let's assume we're processing award travel data
        # and we want to extract the destination and price
        destination = data.split(",")[0]
        price = data.split(",")[1]
        return {"destination": destination, "price": price}

class RedisClient:
    def __init__(self):
        self.redis = None

    async def connect(self):
        import aioredis
        self.redis = aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")

    async def set(self, data):
        if not self.redis:
            await self.connect()
        await self.redis.set("award_travel_data", str(data))
