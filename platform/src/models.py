from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Award(Base):
    __tablename__ = "awards"
    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    travel_date = Column(String)
    award_type = Column(String)
    award_level = Column(String)
