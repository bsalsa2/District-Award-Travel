from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sqlite3
import numpy as np

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('payment_gateway.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments
    (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, payment_method TEXT)
''')

# Commit changes and close connection
conn.commit()
conn.close()

# Define payment gateway API endpoint
@app.post("/payment")
async def make_payment(request: Request):
    # Get payment details from request body
    payment_details = await request.json()

    # Validate payment details
    if not payment_details.get('user_id') or not payment_details.get('amount') or not payment_details.get('payment_method'):
        return JSONResponse({"error": "Invalid payment details"}, status_code=400)

    # Connect to SQLite database
    conn = sqlite3.connect('payment_gateway.db')
    cursor = conn.cursor()

    # Insert payment details into database
    cursor.execute('''
        INSERT INTO payments (user_id, amount, payment_method)
        VALUES (?, ?, ?)
    ''', (payment_details['user_id'], payment_details['amount'], payment_details['payment_method']))

    # Commit changes and close connection
    conn.commit()
    conn.close()

    # Return success response
    return JSONResponse({"message": "Payment successful"}, status_code=200)
