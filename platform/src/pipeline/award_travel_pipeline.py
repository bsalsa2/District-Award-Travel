import sqlite3
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('award_travel.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS award_travel_routes
    (id INTEGER PRIMARY KEY, route TEXT, flight_schedule TEXT, availability TEXT, price REAL)
''')

# Define a function to update award travel routes
def update_award_travel_routes(routes: List[Dict]):
    cursor.executemany('''
        INSERT OR REPLACE INTO award_travel_routes (id, route, flight_schedule, availability, price)
        VALUES (?, ?, ?, ?, ?)
    ''', [(route['id'], route['route'], route['flight_schedule'], route['availability'], route['price']) for route in routes])
    conn.commit()

# Define a function to get award travel routes
def get_award_travel_routes():
    cursor.execute('SELECT * FROM award_travel_routes')
    return cursor.fetchall()

# Define a route to update award travel routes
@app.post('/update_award_travel_routes')
async def update_routes(routes: List[Dict]):
    update_award_travel_routes(routes)
    return JSONResponse(content={'message': 'Award travel routes updated successfully'}, status_code=200)

# Define a route to get award travel routes
@app.get('/get_award_travel_routes')
async def get_routes():
    routes = get_award_travel_routes()
    return JSONResponse(content=[{'id': route[0], 'route': route[1], 'flight_schedule': route[2], 'availability': route[3], 'price': route[4]} for route in routes], status_code=200)
