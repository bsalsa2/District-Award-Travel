import asyncio
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define database connection URL
DATABASE_URL = "sqlite:///district-award-travel.db"

# Create a database engine
engine = create_engine(DATABASE_URL)

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a base class for declarative models
Base = declarative_base()

# Define a data model
class Data(Base):
    __tablename__ = "data"
    id = Column(Integer, primary_key=True)
    column1 = Column(String)
    column2 = Column(String)

# Create all tables in the engine
Base.metadata.create_all(engine)

class Database:
    def __init__(self):
        self.session = Session()

    async def fetch_data(self):
        # Fetch data from the database
        data = self.session.query(Data).all()
        return [{"id": d.id, "column1": d.column1, "column2": d.column2} for d in data]
