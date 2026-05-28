from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging
import json

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the payment gateway webhook endpoint
@app.post("/payment-gateway-webhook")
async def payment_gateway_webhook(request: Request):
    # Get the request body
    request_body = await request.json()

    # Log the request body
    logger.info(f"Received payment gateway notification: {request_body}")

    # Process the payment gateway notification
    if request_body["event"] == "payment_succeeded":
        # Update the payment status in the database
        update_payment_status(request_body["payment_id"], "succeeded")
    elif request_body["event"] == "payment_failed":
        # Update the payment status in the database
        update_payment_status(request_body["payment_id"], "failed")

    # Return a success response
    return JSONResponse(content={"message": "Payment gateway notification received successfully"}, status_code=200)

def update_payment_status(payment_id, status):
    # Connect to the database
    import sqlite3
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Update the payment status
    cursor.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
    conn.commit()
    conn.close()
