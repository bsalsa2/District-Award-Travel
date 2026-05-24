import sqlite3
import json
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.requests import Request

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('user_profiles.db')
cursor = conn.cursor()

# Function to update user profile
def update_user_profile(username, email, award_points, travel_history):
    cursor.execute('UPDATE user_profiles SET email = ?, award_points = ?, travel_history = ? WHERE username = ?', (email, award_points, travel_history, username))
    conn.commit()

# API endpoint to update user profile
@app.post("/update_user_profile")
async def update_user_profile_api(request: Request):
    data = await request.json()
    username = data["username"]
    email = data["email"]
    award_points = data["award_points"]
    travel_history = data["travel_history"]
    update_user_profile(username, email, award_points, travel_history)
    return JSONResponse(content={"message": "User profile updated successfully"}, media_type="application/json")

# Function to add new user profile
def add_new_user_profile(username, email, award_points, travel_history):
    cursor.execute('INSERT INTO user_profiles (username, email, award_points, travel_history) VALUES (?, ?, ?, ?)', (username, email, award_points, travel_history))
    conn.commit()

# API endpoint to add new user profile
@app.post("/add_new_user_profile")
async def add_new_user_profile_api(request: Request):
    data = await request.json()
    username = data["username"]
    email = data["email"]
    award_points = data["award_points"]
    travel_history = data["travel_history"]
    add_new_user_profile(username, email, award_points, travel_history)
    return JSONResponse(content={"message": "New user profile added successfully"}, media_type="application/json")
