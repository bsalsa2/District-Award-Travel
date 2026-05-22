import sqlite3
import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

# Define the user model
class User(BaseModel):
    id: int
    username: str
    password: str

# Create a database connection
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Create the users table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY, username TEXT, password TEXT)
''')

# Define the authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Define the FastAPI app
app = FastAPI()

# Define the authentication endpoint
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Query the database for the user
    cursor.execute('SELECT * FROM users WHERE username = ?', (form_data.username,))
    user = cursor.fetchone()

    # Check if the user exists and the password is correct
    if user and user[2] == form_data.password:
        # Return the access token
        return {"access_token": user[0], "token_type": "bearer"}
    else:
        # Raise an exception if the authentication fails
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Define the protected endpoint
@app.get("/protected")
async def protected(token: str = Depends(oauth2_scheme)):
    # Query the database for the user
    cursor.execute('SELECT * FROM users WHERE id = ?', (int(token),))
    user = cursor.fetchone()

    # Check if the user exists
    if user:
        # Return the user's data
        return {"username": user[1]}
    else:
        # Raise an exception if the user does not exist
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
