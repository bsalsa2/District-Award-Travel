import numpy as np
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from typing import List, Dict

app = FastAPI()

class PaymentGatewayPipeline:
    def __init__(self):
        self.payment_gateway = PaymentGateway()

    def process_payment(self, user_id: int, flight_id: int, payment_method: str):
        # Process payment using payment gateway API
        payment_response = self.payment_gateway.process_payment(user_id, flight_id, payment_method)
        if payment_response["status"] != "success":
            return JSONResponse(content={"error": "Payment processing failed"}, status_code=400)

        return JSONResponse(content={"message": "Payment processed successfully"}, status_code=200)

class PaymentGateway:
    def process_payment(self, user_id: int, flight_id: int, payment_method: str):
        # Process payment using payment gateway API
        # For simplicity, assume we have a mock payment gateway
        return {"status": "success"}

@app.post("/process_payment")
async def process_payment(user_id: int, flight_id: int, payment_method: str):
    payment_gateway_pipeline = PaymentGatewayPipeline()
    return payment_gateway_pipeline.process_payment(user_id, flight_id, payment_method)
