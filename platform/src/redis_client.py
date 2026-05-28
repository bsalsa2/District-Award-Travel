import redis
import asyncio

class RedisClient:
    def __init__(self):
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)

    async def set_data(self, data):
        self.redis_client.set("data", data)

    async def get_data(self):
        return self.redis_client.get("data")

    async def set_analytics(self, data):
        self.redis_client.set("analytics", data)

    async def get_analytics(self):
        return self.redis_client.get("analytics")
