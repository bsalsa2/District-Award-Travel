from dataclasses import dataclass
from typing import Optional

@dataclass
class AwardFlightBooking:
    id: int
    price: float
    card_number: str
    expiration_month: int
    expiration_year: int
    cvv: str

@dataclass
class PaymentGatewayConfig:
    base_url: str
    api_key: str
