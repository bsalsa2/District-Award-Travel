import asyncio
from platform.src.redis_client import RedisClient
from platform.src.sqlalchemy_client import SQLAlchemyClient
from platform.src.models import AwardTravelData

class StreamProcessor:
    def __init__(self, redis_client, sqlalchemy_client):
        self.redis_client = redis_client
        self.sqlalchemy_client = sqlalchemy_client

    async def process_stream(self):
        while True:
            data = await self.redis_client.get_stream_data()
            if data:
                award_travel_data = AwardTravelData(**data)
                await self.sqlalchemy_client.insert_data(award_travel_data)
                await asyncio.sleep(0.1)
