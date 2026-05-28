import asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker
from platform.src.redis_client import RedisClient

Base = declarative_base()

class Data(Base):
    __tablename__ = "data"
    id = Column(Integer, primary_key=True)
    value = Column(String)

class DataPipeline:
    def __init__(self):
        self.engine = create_engine("sqlite:///data.db")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.redis_client = RedisClient()

    def get_data(self):
        data = self.session.query(Data).all()
        return [{"id": d.id, "value": d.value} for d in data]

    async def process_data(self, data):
        self.redis_client.set_data(data)
        self.session.add(Data(value=data))
        self.session.commit()

    async def start_pipeline(self):
        while True:
            data = await self.redis_client.get_data()
            if data:
                await self.process_data(data)
            await asyncio.sleep(1)
