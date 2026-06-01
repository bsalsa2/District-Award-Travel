from pydantic import BaseModel

class AwardTravel(BaseModel):
    id: int
    description: str
    availability: str
    pricing: str

class Availability(BaseModel):
    query: str
    availability: str

class Pricing(BaseModel):
    query: str
    pricing: str
