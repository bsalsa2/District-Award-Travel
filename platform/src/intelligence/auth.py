import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlite3 import Error

# Define the user model
class User(BaseModel):
    id: int
    username: str
    email: str
    password: str

# Define the authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Initialize the FastAPI app
app = FastAPI()

# Define the user database
users_db = {
    "user1": {
        "username": "user1",
        "email": "user1@example.com",
        "password": "password1"
    },
    "user2": {
        "username": "user2",
        "email": "user2@example.com",
        "password": "password2"
    }
}

# Define the authentication function
def authenticate_user(username: str, password: str):
    if username in users_db:
        user = users_db[username]
        if user["password"] == password:
            return user
    return None

# Define the login endpoint
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": user["username"], "token_type": "bearer"}

# Define the protected endpoint
@app.get("/protected")
async def protected(token: str = Depends(oauth2_scheme)):
    return {"message": f"Hello, {token}!"}
