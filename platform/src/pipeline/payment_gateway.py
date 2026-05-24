import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class PaymentRequest(BaseModel):
    user_id: int
    award_id: int
    payment_method: str
    amount: float

class PaymentResponse(BaseModel):
    payment_id: int
    status: str

@app.post("/payment")
async def process_payment(payment_request: PaymentRequest):
    try:
        # Connect to database
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Insert payment into database
        cursor.execute("INSERT INTO payments (user_id, award_id, payment_method, amount) VALUES (?, ?, ?, ?)",
                        (payment_request.user_id, payment_request.award_id, payment_request.payment_method, payment_request.amount))
        payment_id = cursor.lastrowid
        conn.commit()

        # Update award status
        cursor.execute("UPDATE awards SET status = 'booked' WHERE id = ?", (payment_request.award_id,))
        conn.commit()

        # Close database connection
        conn.close()

        return PaymentResponse(payment_id=payment_id, status="success")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
