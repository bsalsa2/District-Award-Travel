import aioredis

class RedisClient:
    def __init__(self):
        self.redis = None

    async def connect(self):
        from platform.src.config import settings
        self.redis = aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")

    async def set(self, data):
        if not self.redis:
            await self.connect()
        await self.redis.set("award_travel_data", str(data))
