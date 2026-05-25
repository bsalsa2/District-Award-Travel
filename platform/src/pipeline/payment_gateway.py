import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import Dict

app = FastAPI()

class PaymentGateway:
    def __init__(self):
        self.payment_methods = [
            {"id": 1, "method": "credit_card"},
            {"id": 2, "method": "paypal"},
        ]

    def process_payment(self, payment_method_id: int, amount: int) -> bool:
        # Simulate payment processing
        return True

@app.post("/process_payment")
async def process_payment(payment_method_id: int, amount: int):
    payment_gateway = PaymentGateway()
    payment_processed = payment_gateway.process_payment(payment_method_id, amount)
    return JSONResponse(content={"payment_processed": payment_processed}, media_type="application/json")
