from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Create a SQLite database engine
engine = create_engine('sqlite:///platform/db.sqlite3')

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a base class for declarative class definitions
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
    balance = Column(Integer)

class AwardSearch(Base):
    __tablename__ = 'award_searches'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    origin = Column(String)
    destination = Column(String)
    cabin = Column(String)
    status = Column(String)

class BookingPipeline(Base):
    __tablename__ = 'booking_pipeline'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    airline = Column(String)
    route = Column(String)
    cabin = Column(String)
    miles_required = Column(Integer)
    status = Column(String)

# Create all tables in the engine
Base.metadata.create_all(engine)
