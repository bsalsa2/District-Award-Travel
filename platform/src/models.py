from dataclasses import dataclass
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

@dataclass
class AwardTravelRoute:
    id: int
    origin: str
    destination: str
    airline: str
    award_price: int

    def to_dict(self):
        return {
            "id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "airline": self.airline,
            "award_price": self.award_price
        }

class AwardTravelRouteModel(Base):
    __tablename__ = "award_travel_routes"

    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    airline = Column(String)
    award_price = Column(Integer)
