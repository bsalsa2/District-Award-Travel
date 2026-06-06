import sqlite3
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserProfile(BaseModel):
    user_id: int
    name: str
    email: str

class AwardTravelData(BaseModel):
    user_id: int
    travel_date: str
    destination: str
    points_used: int

def integrate_data():
    conn = sqlite3.connect('district_award_travel.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS award_travel_data (
            user_id INTEGER,
            travel_date TEXT,
            destination TEXT,
            points_used INTEGER,
            FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        )
    ''')

    cursor.execute('''
        SELECT * FROM user_profiles
    ''')

    user_profiles = cursor.fetchall()

    for profile in user_profiles:
        user_id = profile[0]
        cursor.execute('''
            SELECT * FROM award_travel_data
            WHERE user_id = ?
        ''', (user_id,))

        award_travel_data = cursor.fetchall()

        # Integrate award travel data with user profiles
        integrated_data = {
            'user_id': user_id,
            'name': profile[1],
            'email': profile[2],
            'travel_history': award_travel_data
        }

        yield integrated_data

    conn.close()

@app.get('/integrated_data')
async def get_integrated_data():
    integrated_data = list(integrate_data())
    return integrated_data
