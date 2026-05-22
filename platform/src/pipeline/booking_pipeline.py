from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import numpy as np
import sqlite3
from typing import Dict

app = FastAPI()

# Connect to the SQLite database
conn = sqlite3.connect('bookings.db')
cursor = conn.cursor()

# Create the bookings table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        flight_id INTEGER,
        departure_date DATE,
        return_date DATE,
        status TEXT
    )
''')

# Commit the changes
conn.commit()

# Define a function to book a flight
def book_flight(user_id: int, flight_id: int, departure_date: str, return_date: str):
    # Insert the booking into the database
    cursor.execute('''
        INSERT INTO bookings (user_id, flight_id, departure_date, return_date, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, flight_id, departure_date, return_date))
    conn.commit()
    return cursor.lastrowid

# Define a function to get all bookings for a user
def get_bookings(user_id: int):
    cursor.execute('''
        SELECT * FROM bookings
        WHERE user_id = ?
    ''', (user_id,))
    return cursor.fetchall()

# Define a route to book a flight
@app.post('/book_flight')
async def book_flight_route(request: Request):
    data = await request.json()
    user_id = data['user_id']
    flight_id = data['flight_id']
    departure_date = data['departure_date']
    return_date = data['return_date']
    booking_id = book_flight(user_id, flight_id, departure_date, return_date)
    return JSONResponse({'booking_id': booking_id}, status_code=201)

# Define a route to get all bookings for a user
@app.get('/get_bookings/{user_id}')
async def get_bookings_route(user_id: int):
    bookings = get_bookings(user_id)
    return JSONResponse([{'id': booking[0], 'user_id': booking[1], 'flight_id': booking[2], 'departure_date': booking[3], 'return_date': booking[4], 'status': booking[5]} for booking in bookings], status_code=200)
