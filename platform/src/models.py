from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AwardFlight(Base):
    __tablename__ = 'award_flights'
    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    airline = Column(String)
    award_availability = Column(Integer)
