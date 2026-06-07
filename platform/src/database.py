from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import Base

# Create a database engine and session maker
engine = create_engine('sqlite:///district_award_travel.db')
Session = sessionmaker(bind=engine)

# Create the database tables
Base.metadata.create_all(engine)
