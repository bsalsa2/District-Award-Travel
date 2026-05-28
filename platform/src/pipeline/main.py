from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging
import uvicorn

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the make payment endpoint
@app.post("/make-payment")
async def make_payment(amount: int):
    # Create a payment using the payment gateway
    payment_id = create_payment(amount)

    # Return the payment gateway URL
    return JSONResponse(content={"payment_gateway_url": f"https://example.com/payment/{payment_id}"}, status_code=200)

def create_payment(amount):
    # Connect to the database
    import sqlite3
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Create a new payment
    cursor.execute("INSERT INTO payments (payment_id, status) VALUES (?, ?)", (str(amount), "pending"))
    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return payment_id

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
