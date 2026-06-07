import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class PaymentRequest(BaseModel):
    user_id: int
    flight_id: int
    amount: float

class PaymentResponse(BaseModel):
    payment_id: int
    status: str

# Connect to SQLite database
conn = sqlite3.connect('district_award_travel.db')
cursor = conn.cursor()

# Create payment table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        flight_id INTEGER,
        amount REAL,
        status TEXT
    )
''')

# Commit changes and close connection
conn.commit()
conn.close()

# Define payment gateway API endpoint
@app.post("/payment", response_model=PaymentResponse)
async def make_payment(payment_request: PaymentRequest):
    # Connect to SQLite database
    conn = sqlite3.connect('district_award_travel.db')
    cursor = conn.cursor()

    # Insert payment into database
    cursor.execute('''
        INSERT INTO payments (user_id, flight_id, amount, status)
        VALUES (?, ?, ?, 'pending')
    ''', (payment_request.user_id, payment_request.flight_id, payment_request.amount))

    # Get payment ID
    payment_id = cursor.lastrowid

    # Commit changes and close connection
    conn.commit()
    conn.close()

    # Return payment response
    return PaymentResponse(payment_id=payment_id, status='pending')
