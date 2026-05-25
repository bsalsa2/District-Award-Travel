from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlite3 import Error
import sqlite3
import numpy as np

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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Create a FastAPI app
app = FastAPI()

# Create a connection to the database
conn = create_connection()

# Create a cursor object
cur = conn.cursor()

# Create the users table if it doesn't exist
cur.execute('''
    CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY, username TEXT, password TEXT)
''')

# Define the login endpoint
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Query the database for the user
    cur.execute("SELECT * FROM users WHERE username = ?", (form_data.username,))
    user = cur.fetchone()

    # Check if the user exists and the password is correct
    if user and user[2] == form_data.password:
        # Return a token
        return {"access_token": user[1], "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

# Define the register endpoint
@app.post("/register")
async def register(username: str, password: str):
    # Check if the user already exists
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Insert the new user into the database
    cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()

    # Return a success message
    return {"message": "User created successfully"}

# Define the protected endpoint
@app.get("/protected")
async def protected(token: str = Depends(oauth2_scheme)):
    # Query the database for the user
    cur.execute("SELECT * FROM users WHERE username = ?", (token,))
    user = cur.fetchone()

    # Check if the user exists
    if user:
        # Return a success message
        return {"message": "Hello, " + user[1]}
    else:
        raise HTTPException(status_code=401, detail="Invalid token")
