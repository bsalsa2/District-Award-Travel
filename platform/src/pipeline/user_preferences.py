import sqlite3
from fastapi import Depends, FastAPI
from pydantic import BaseModel

app = FastAPI()

# Define the user preferences model
class UserPreferences(BaseModel):
    username: str
    preferred_airlines: list[str]
    preferred_destinations: list[str]

# Connect to the database
conn = sqlite3.connect('user_preferences.db')
cursor = conn.cursor()

# Create the user preferences table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_preferences
    (username TEXT PRIMARY KEY, preferred_airlines TEXT, preferred_destinations TEXT)
''')

# Define the function to get user preferences
def get_user_preferences(username: str):
    cursor.execute('SELECT * FROM user_preferences WHERE username = ?', (username,))
    user_preferences = cursor.fetchone()
    if user_preferences:
        return user_preferences
    else:
        return None

# Define the endpoint to get user preferences
@app.get("/user_preferences")
async def get_preferences(username: str):
    user_preferences = get_user_preferences(username)
    if user_preferences:
        return {"username": user_preferences[0], "preferred_airlines": user_preferences[1].split(","), "preferred_destinations": user_preferences[2].split(",")}
    else:
        return {"message": "User preferences not found"}
