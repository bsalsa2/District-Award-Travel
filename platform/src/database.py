from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import Base

engine = create_engine('sqlite:///award_flights.db')
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)
