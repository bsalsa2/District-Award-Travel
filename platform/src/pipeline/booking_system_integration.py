import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class BookingRequest(BaseModel):
    date: str
    destination: str

@app.post("/book")
async def book(booking_request: BookingRequest):
    # Connect to the database
    conn = sqlite3.connect('booking_database.db')
    cursor = conn.cursor()

    # Check availability
    cursor.execute('SELECT availability FROM award_travel_data WHERE date=? AND destination=?', (booking_request.date, booking_request.destination))
    availability = cursor.fetchone()
    if availability is None or availability[0] == 0:
        raise HTTPException(status_code=404, detail='No availability')

    # Book the award travel
    cursor.execute('INSERT INTO bookings (date, destination) VALUES (?, ?)', (booking_request.date, booking_request.destination))
    conn.commit()
    conn.close()
    return {'message': 'Booking successful'}

@app.get("/availability")
async def get_availability(date: str, destination: str):
    # Connect to the database
    conn = sqlite3.connect('booking_database.db')
    cursor = conn.cursor()

    # Get availability
    cursor.execute('SELECT availability FROM award_travel_data WHERE date=? AND destination=?', (date, destination))
    availability = cursor.fetchone()
    if availability is None:
        return {'availability': 0}
    else:
        return {'availability': availability[0]}
