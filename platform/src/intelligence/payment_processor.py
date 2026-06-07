import numpy as np
from platform.src.pipeline.payment_gateway import app

class PaymentProcessor:
    def __init__(self):
        self.payment_gateway = app

    def process_payment(self, payment_request):
        # Make payment request to payment gateway
        response = self.payment_gateway.post("/payment", json=payment_request.dict())

        # Check if payment was successful
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception("Payment failed")
