from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AwardTravelData(Base):
    __tablename__ = "award_travel_data"
    id = Column(Integer, primary_key=True)
    route = Column(String)
    airline = Column(String)
    award_type = Column(String)
    availability = Column(Integer)

    def __init__(self, route, airline, award_type, availability):
        self.route = route
        self.airline = airline
        self.award_type = award_type
        self.availability = availability
