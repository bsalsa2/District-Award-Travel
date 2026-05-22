import asyncio
from platform.src.redis_client import RedisClient
from platform.src.airline_api import AirlineAPI
from platform.src.data_processor import DataProcessor

class DataPipeline:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.airline_api = AirlineAPI()
        self.data_processor = DataProcessor()

    async def start(self):
        await self.airline_api.connect()
        await self.data_processor.start()

    async def get_award_prices(self):
        award_prices = await self.redis_client.get("award_prices")
        if award_prices is None:
            award_prices = await self.airline_api.get_award_prices()
            await self.redis_client.set("award_prices", award_prices)
        return award_prices

    async def get_award_availability(self):
        award_availability = await self.redis_client.get("award_availability")
        if award_availability is None:
            award_availability = await self.airline_api.get_award_availability()
            await self.redis_client.set("award_availability", award_availability)
        return award_availability
