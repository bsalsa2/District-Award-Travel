import asyncio
import redis

class RedisClient:
    def __init__(self):
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)

    async def get_stream_data(self):
        data = self.redis_client.lpop("stream_data")
        if data:
            return eval(data.decode("utf-8"))
        return None
