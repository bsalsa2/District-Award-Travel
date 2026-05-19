from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    points_balances = relationship('PointsBalance', backref='client')
    award_searches = relationship('AwardSearch', backref='client')
    booking_pipeline = relationship('BookingPipeline', backref='client')

class PointsBalance(Base):
    __tablename__ = 'points_balances'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    program_name = Column(String)
    balance = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)

class AwardSearch(Base):
    __tablename__ = 'award_searches'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    origin = Column(String)
    destination = Column(String)
    cabin = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class BookingPipeline(Base):
    __tablename__ = 'booking_pipeline'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    airline = Column(String)
    route = Column(String)
    cabin = Column(String)
    miles_required = Column(Float)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
