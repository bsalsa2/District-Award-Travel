from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlite3 import Error
import sqlite3
import numpy as np

app = FastAPI()

# Define the database connection
def create_connection():
    conn = None
    try:
        conn = sqlite3.connect('database.db')
        return conn
    except Error as e:
        print(e)

# Define the user model
class User(BaseModel):
    id: int
    username: str
    password: str

# Define the authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create a connection to the database
conn = create_connection()

# Create the users table if it does not exist
def create_table():
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )""")
        conn.commit()
    except Error as e:
        print(e)

# Create the users table
create_table()

# Define the authentication endpoint
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Query the database for the user
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (form_data.username,))
    user = c.fetchone()

    # Check if the user exists and the password is correct
    if user and user[2] == form_data.password:
        # Return the access token
        return {"access_token": user[1], "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

# Define the protected endpoint
@app.get("/protected")
async def protected(token: str = Depends(oauth2_scheme)):
    # Query the database for the user
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (token,))
    user = c.fetchone()

    # Check if the user exists
    if user:
        # Return the user's data
        return {"id": user[0], "username": user[1]}
    else:
        raise HTTPException(status_code=401, detail="Invalid token")
