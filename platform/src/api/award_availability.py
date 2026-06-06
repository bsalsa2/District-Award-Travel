from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from platform.src.database.availability_db import AvailabilityDB

app = FastAPI()

class SearchRequest(BaseModel):
    origin: str
    destination: str
    date_from: str
    date_to: str
    cabin: str

class AvailabilityResponse(BaseModel):
    airline: str
    origin: str
    destination: str
    date: str
    cabin: str
    miles_required: int
    taxes_usd: float
    available_seats: int
    program_name: str

db = AvailabilityDB('availability.db')

@app.post("/search")
async def search_availability(request: SearchRequest):
    airlines = ['United', 'American', 'Delta', 'Air Canada', 'Turkish']
    availability = []
    for airline in airlines:
        availability.append({
            'airline': airline,
            'origin': request.origin,
            'destination': request.destination,
            'date': request.date_from,
            'cabin': request.cabin,
            'miles_required': 10000,
            'taxes_usd': 100.0,
            'available_seats': 5,
            'program_name': 'Mock Program'
        })
        db.insert_availability({
            'airline': airline,
            'origin': request.origin,
            'destination': request.destination,
            'date': request.date_from,
            'cabin': request.cabin,
            'miles_required': 10000,
            'taxes_usd': 100.0,
            'available_seats': 5,
            'program_name': 'Mock Program'
        })
    return availability

@app.get("/search/history")
async def get_search_history():
    searches = db.get_last_searches()
    return searches
