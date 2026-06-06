from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlite3
import json

app = FastAPI()

# Define the award flight data model
class AwardFlight(BaseModel):
    id: int
    airline: str
    departure: str
    arrival: str
    date: str
    award_price: int

# Create a SQLite database engine
engine = create_engine('sqlite:///award_flights.db')

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a base class for declarative class definitions
Base = declarative_base()

# Define the award flights table
class AwardFlights(Base):
    __tablename__ = 'award_flights'
    id = Column(Integer, primary_key=True)
    airline = Column(String)
    departure = Column(String)
    arrival = Column(String)
    date = Column(String)
    award_price = Column(Integer)

# Create the award flights table
Base.metadata.create_all(engine)

# Define the endpoint to ingest award flight data
@app.post("/award_flights/")
async def create_award_flight(award_flight: AwardFlight):
    # Create a new session
    session = Session()

    # Add the award flight to the session
    session.add(AwardFlights(
        id=award_flight.id,
        airline=award_flight.airline,
        departure=award_flight.departure,
        arrival=award_flight.arrival,
        date=award_flight.date,
        award_price=award_flight.award_price
    ))

    # Commit the changes
    session.commit()

    # Close the session
    session.close()

    # Return a success message
    return {"message": "Award flight data ingested successfully"}

# Define the endpoint to retrieve award flight data
@app.get("/award_flights/")
async def read_award_flights():
    # Create a new session
    session = Session()

    # Query the award flights table
    award_flights = session.query(AwardFlights).all()

    # Close the session
    session.close()

    # Return the award flight data
    return [{"id": flight.id, "airline": flight.airline, "departure": flight.departure, "arrival": flight.arrival, "date": flight.date, "award_price": flight.award_price} for flight in award_flights]
