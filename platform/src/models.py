from pydantic import BaseModel
from typing import List

class AwardSearchRequest(BaseModel):
    origin: str
    destination: str
    travel_dates: List[str]
    loyalty_program: str
    airline_partnerships: List[str]

class AwardSearchResult(BaseModel):
    airline: str
    route: str
    travel_dates: List[str]
    loyalty_program: str
    award_price: int
