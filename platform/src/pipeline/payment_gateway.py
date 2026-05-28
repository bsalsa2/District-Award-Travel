from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import sqlite3
import numpy as np

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('payment_gateway.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments
    (id INTEGER PRIMARY KEY, amount REAL, payment_method TEXT, status TEXT)
''')

# Insert payment into database
def insert_payment(amount, payment_method, status):
    cursor.execute('INSERT INTO payments (amount, payment_method, status) VALUES (?, ?, ?)', (amount, payment_method, status))
    conn.commit()

# Get all payments from database
def get_payments():
    cursor.execute('SELECT * FROM payments')
    return cursor.fetchall()

# Payment gateway endpoint
@app.post("/payment")
async def make_payment(request: Request):
    try:
        # Get payment details from request body
        payment_details = await request.json()
        amount = payment_details['amount']
        payment_method = payment_details['payment_method']

        # Process payment
        insert_payment(amount, payment_method, 'pending')

        # Return success response
        return JSONResponse(content={'message': 'Payment successful'}, status_code=200)
    except Exception as e:
        # Return error response
        return JSONResponse(content={'message': str(e)}, status_code=400)

# Payment status endpoint
@app.get("/payment/{payment_id}")
async def get_payment_status(payment_id: int):
    try:
        # Get payment status from database
        cursor.execute('SELECT status FROM payments WHERE id = ?', (payment_id,))
        payment_status = cursor.fetchone()

        # Return payment status
        return JSONResponse(content={'status': payment_status[0]}, status_code=200)
    except Exception as e:
        # Return error response
        return JSONResponse(content={'message': str(e)}, status_code=400)
