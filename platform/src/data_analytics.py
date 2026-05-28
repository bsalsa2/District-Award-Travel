import asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker
from platform.src.redis_client import RedisClient

Base = declarative_base()

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True)
    value = Column(String)

class DataAnalytics:
    def __init__(self):
        self.engine = create_engine("sqlite:///analytics.db")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.redis_client = RedisClient()

    def get_analytics(self):
        analytics = self.session.query(Analytics).all()
        return [{"id": a.id, "value": a.value} for a in analytics]

    async def process_analytics(self, data):
        self.redis_client.set_analytics(data)
        self.session.add(Analytics(value=data))
        self.session.commit()

    async def start_analytics(self):
        while True:
            data = await self.redis_client.get_analytics()
            if data:
                await self.process_analytics(data)
            await asyncio.sleep(1)
