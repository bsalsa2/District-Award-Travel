import sqlite3
import numpy as np
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List

app = FastAPI()

# Connect to the database
conn = sqlite3.connect('district_award_travel.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS award_travel_routes
    (id INTEGER PRIMARY KEY, route TEXT, user_id INTEGER)
''')

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_notifications
    (id INTEGER PRIMARY KEY, user_id INTEGER, notification TEXT)
''')

# Function to update award travel routes
def update_award_travel_routes(route: str, user_id: int):
    cursor.execute('''
        INSERT INTO award_travel_routes (route, user_id)
        VALUES (?, ?)
    ''', (route, user_id))
    conn.commit()

# Function to notify users of changes to their booked flights
def notify_users(user_id: int, notification: str):
    cursor.execute('''
        INSERT INTO user_notifications (user_id, notification)
        VALUES (?, ?)
    ''', (user_id, notification))
    conn.commit()

# API endpoint to update award travel routes
@app.post("/update_award_travel_routes")
async def update_award_travel_routes_endpoint(route: str, user_id: int):
    update_award_travel_routes(route, user_id)
    notify_users(user_id, f"Your award travel route has been updated to {route}")
    return JSONResponse(content={"message": "Award travel route updated successfully"}, status_code=200)

# API endpoint to get user notifications
@app.get("/get_user_notifications")
async def get_user_notifications(user_id: int):
    cursor.execute('''
        SELECT notification FROM user_notifications
        WHERE user_id = ?
    ''', (user_id,))
    notifications = cursor.fetchall()
    return JSONResponse(content={"notifications": [notification[0] for notification in notifications]}, status_code=200)
