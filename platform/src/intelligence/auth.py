import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

app = FastAPI()

# Define the user model
class User(BaseModel):
    username: str
    email: str
    award_points: int

# Define the authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Define the user database (in-memory for simplicity)
users_db = {
    "user1": {"username": "user1", "email": "user1@example.com", "award_points": 1000},
    "user2": {"username": "user2", "email": "user2@example.com", "award_points": 500},
}

# Define the authentication endpoint
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if user["username"] != form_data.username or user["email"] != form_data.username:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": user["username"], "token_type": "bearer"}

# Define the protected endpoint
@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    user = users_db.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
