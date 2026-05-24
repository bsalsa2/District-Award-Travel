import asyncio
from platform.src.models import AwardTravelRoute
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class AwardTravelRepository:
    def __init__(self):
        self.engine = create_engine("sqlite:///award_travel.db")
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def search_award_travel(self, entities):
        session = self.Session()
        routes = session.query(AwardTravelRoute).filter(AwardTravelRoute.origin.in_(entities)).all()
        return [route.to_dict() for route in routes]
