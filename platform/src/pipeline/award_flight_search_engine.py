import sqlite3
import numpy as np
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class AwardFlightSearchRequest(BaseModel):
    origin: str
    destination: str
    travel_date: str
    loyalty_program: str

class AwardFlightSearchResponse(BaseModel):
    flights: list

def get_award_flights(db: sqlite3.Connection, request: AwardFlightSearchRequest):
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM award_flights
        WHERE origin = ? AND destination = ? AND travel_date = ? AND loyalty_program = ?
    """, (request.origin, request.destination, request.travel_date, request.loyalty_program))
    return cursor.fetchall()

@app.post("/award_flights", response_model=AwardFlightSearchResponse)
async def search_award_flights(request: AwardFlightSearchRequest):
    db = sqlite3.connect("award_flights.db")
    flights = get_award_flights(db, request)
    db.close()
    return {"flights": flights}
