import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import AwardAvailability, AwardPricing

class DataPipeline:
    def __init__(self):
        self.engine = create_engine("sqlite:///award_travel.db")
        self.Session = sessionmaker(bind=self.engine)

    async def get_award_availability(self):
        async with self.Session() as session:
            query = session.query(AwardAvailability)
            results = await query.all()
            return [result.to_dict() for result in results]

    async def get_award_pricing(self):
        async with self.Session() as session:
            query = session.query(AwardPricing)
            results = await query.all()
            return [result.to_dict() for result in results]

    async def ingest_award_availability(self, data):
        async with self.Session() as session:
            for item in data:
                award_availability = AwardAvailability(**item)
                session.add(award_availability)
            await session.commit()

    async def ingest_award_pricing(self, data):
        async with self.Session() as session:
            for item in data:
                award_pricing = AwardPricing(**item)
                session.add(award_pricing)
            await session.commit()
