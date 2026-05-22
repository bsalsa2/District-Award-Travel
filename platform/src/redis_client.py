import asyncio
import aioredis

class RedisClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.redis = None

    async def connect(self):
        self.redis = await aioredis.from_url(f"redis://{self.host}:{self.port}")

    async def get(self, key):
        return await self.redis.get(key)

    async def set(self, key, value):
        await self.redis.set(key, value)
