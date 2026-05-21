from pydantic import BaseModel

class Award(BaseModel):
    id: int
    name: str
    description: str
    points_required: int

class User(BaseModel):
    id: int
    name: str
    email: str
    points_balance: int
