import sqlite3
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

app = FastAPI()

# Define the user model
class User(BaseModel):
    username: str
    email: str
    password: str

# Define the authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Connect to the database
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Create the users table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users
    (username TEXT PRIMARY KEY, email TEXT, password TEXT)
''')

# Define the authentication function
def authenticate_user(username: str, password: str):
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    if user:
        return user
    else:
        return None

# Define the login endpoint
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if user:
        return {"access_token": user[0], "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

# Define the protected endpoint
@app.get("/protected")
async def protected(token: str = Depends(oauth2_scheme)):
    return {"message": "Hello, authenticated user!"}
