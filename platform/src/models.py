from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AwardAvailability(Base):
    __tablename__ = "award_availability"
    id = Column(Integer, primary_key=True)
    award_id = Column(String)
    availability = Column(Integer)

    def to_dict(self):
        return {"award_id": self.award_id, "availability": self.availability}

class AwardPricing(Base):
    __tablename__ = "award_pricing"
    id = Column(Integer, primary_key=True)
    award_id = Column(String)
    price = Column(Integer)

    def to_dict(self):
        return {"award_id": self.award_id, "price": self.price}
