import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

class PaymentGateway:
    def __init__(self):
        self.payment_processor = None

    def process_payment(self, user_id: int, amount: float):
        # Simulate a payment processing system
        # In a real-world scenario, this would be replaced with a real payment gateway
        self.payment_processor = "Payment processed successfully"
        return JSONResponse(content={"message": self.payment_processor}, status_code=200)

    def get_payment_status(self, user_id: int):
        # Simulate a payment status check
        # In a real-world scenario, this would be replaced with a real payment gateway
        return JSONResponse(content={"message": "Payment successful"}, status_code=200)
