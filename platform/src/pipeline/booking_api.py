from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import sqlite3
import numpy as np

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('booking.db')
cursor = conn.cursor()

# Create table if not exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        travel_date DATE,
        destination TEXT,
        payment_status TEXT
    )
''')

# Commit the changes
conn.commit()

# Close the connection
conn.close()

# Define a function to book a travel
def book_travel(user_id, travel_date, destination):
    # Connect to SQLite database
    conn = sqlite3.connect('booking.db')
    cursor = conn.cursor()

    # Insert a new booking
    cursor.execute('''
        INSERT INTO bookings (user_id, travel_date, destination, payment_status)
        VALUES (?, ?, ?, 'pending')
    ''', (user_id, travel_date, destination))

    # Commit the changes
    conn.commit()

    # Get the last inserted id
    booking_id = cursor.lastrowid

    # Close the connection
    conn.close()

    return booking_id

# Define a function to update payment status
def update_payment_status(booking_id, payment_status):
    # Connect to SQLite database
    conn = sqlite3.connect('booking.db')
    cursor = conn.cursor()

    # Update the payment status
    cursor.execute('''
        UPDATE bookings
        SET payment_status = ?
        WHERE id = ?
    ''', (payment_status, booking_id))

    # Commit the changes
    conn.commit()

    # Close the connection
    conn.close()

# Define a route for booking travel
@app.post("/book_travel")
async def book_travel_endpoint(request: Request):
    # Get the request body
    request_body = await request.json()

    # Get the user id, travel date, and destination
    user_id = request_body['user_id']
    travel_date = request_body['travel_date']
    destination = request_body['destination']

    # Book the travel
    booking_id = book_travel(user_id, travel_date, destination)

    # Return the booking id
    return JSONResponse(content={'booking_id': booking_id}, status_code=201)

# Define a route for updating payment status
@app.post("/update_payment_status")
async def update_payment_status_endpoint(request: Request):
    # Get the request body
    request_body = await request.json()

    # Get the booking id and payment status
    booking_id = request_body['booking_id']
    payment_status = request_body['payment_status']

    # Update the payment status
    update_payment_status(booking_id, payment_status)

    # Return a success response
    return JSONResponse(content={'message': 'Payment status updated successfully'}, status_code=200)
