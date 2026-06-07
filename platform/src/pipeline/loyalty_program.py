import sqlite3
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Define the loyalty program model
class LoyaltyProgram(BaseModel):
    user_id: int
    points: int

# Connect to the database
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Create the loyalty program table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS loyalty_program (
        user_id INTEGER PRIMARY KEY,
        points INTEGER DEFAULT 0
    )
''')

# Define the API endpoint to add points to a user's loyalty program
@app.post("/add_points")
async def add_points(loyalty_program: LoyaltyProgram):
    cursor.execute('''
        INSERT OR REPLACE INTO loyalty_program (user_id, points)
        VALUES (?, ?)
    ''', (loyalty_program.user_id, loyalty_program.points))
    conn.commit()
    return {"message": "Points added successfully"}

# Define the API endpoint to get a user's loyalty program points
@app.get("/get_points/{user_id}")
async def get_points(user_id: int):
    cursor.execute('''
        SELECT points FROM loyalty_program
        WHERE user_id = ?
    ''', (user_id,))
    points = cursor.fetchone()
    if points is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"points": points[0]}
