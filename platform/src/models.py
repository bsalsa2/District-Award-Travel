from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

    redemptions = relationship("Redemption", backref="client")

class Redemption(Base):
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    award_flight_details = Column(String)
    travel_dates = Column(String)
    points_redeemed = Column(Integer)
