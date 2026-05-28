from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from typing import Dict
import numpy as np
import sqlite3

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('district_award_travel.db')
cursor = conn.cursor()

# Create table for flight bookings if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS flight_bookings (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        flight_id INTEGER,
        booking_date DATE,
        status TEXT
    )
''')

# Define a function to book a flight
def book_flight(user_id: int, flight_id: int) -> Dict:
    # Check if the flight is available
    cursor.execute('SELECT * FROM flights WHERE id = ?', (flight_id,))
    flight = cursor.fetchone()
    if not flight:
        return {'error': 'Flight not found'}

    # Check if the user has enough points
    cursor.execute('SELECT points FROM users WHERE id = ?', (user_id,))
    user_points = cursor.fetchone()[0]
    if user_points < flight[2]:
        return {'error': 'Not enough points'}

    # Book the flight
    cursor.execute('INSERT INTO flight_bookings (user_id, flight_id, booking_date, status) VALUES (?, ?, DATE(), ?)', (user_id, flight_id, 'booked'))
    conn.commit()
    return {'message': 'Flight booked successfully'}

# Define a route for booking a flight
@app.post('/book_flight')
async def book_flight_route(user_id: int, flight_id: int):
    result = book_flight(user_id, flight_id)
    return JSONResponse(content=result, status_code=200)
