from platform.src.models import AwardSearchRequest, AwardSearchResult
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import asyncio

Base = declarative_base()

class Award(Base):
    __tablename__ = 'awards'
    id = Column(Integer, primary_key=True)
    airline = Column(String)
    route = Column(String)
    travel_dates = Column(String)
    loyalty_program = Column(String)
    award_price = Column(Integer)

class AwardRepository:
    def __init__(self):
        self.engine = create_engine('sqlite:///platform/src/awards.db', poolclass=NullPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    async def search_awards(self, request: AwardSearchRequest):
        session = self.Session()
        results = session.query(Award).filter(
            Award.origin == request.origin,
            Award.destination == request.destination,
            Award.travel_dates.in_(request.travel_dates),
            Award.loyalty_program == request.loyalty_program,
            Award.airline_partnerships.in_(request.airline_partnerships)
        ).all()
        return [AwardSearchResult(
            airline=result.airline,
            route=result.route,
            travel_dates=result.travel_dates.split(','),
            loyalty_program=result.loyalty_program,
            award_price=result.award_price
        ) for result in results]
