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
    username: str
    email: str
    password: str

# Define the authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create the FastAPI app
app = FastAPI()

# Define the authentication endpoint
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Connect to the database
    conn = create_connection()
    cursor = conn.cursor()

    # Query the user
    cursor.execute("SELECT * FROM users WHERE username = ?", (form_data.username,))
    user = cursor.fetchone()

    # Check the password
    if user and user[2] == form_data.password:
        # Generate a token
        token = np.random.randint(0, 1000000)
        return {"access_token": token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

# Define the protected endpoint
@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    # Connect to the database
    conn = create_connection()
    cursor = conn.cursor()

    # Query the user
    cursor.execute("SELECT * FROM users WHERE token = ?", (token,))
    user = cursor.fetchone()

    # Return the user
    if user:
        return {"username": user[1], "email": user[2]}
    else:
        raise HTTPException(status_code=401, detail="Invalid token")
