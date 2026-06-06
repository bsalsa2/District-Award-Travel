import sqlite3
import numpy as np
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('hotel_prices.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS hotel_prices
    (id INTEGER PRIMARY KEY, hotel_name TEXT, price REAL, timestamp TEXT)
''')

# Define a function to fetch hotel prices from a third-party API
def fetch_hotel_prices(hotel_name: str) -> float:
    # Simulate fetching hotel prices from a third-party API
    import random
    return random.uniform(100.0, 500.0)

# Define a function to update hotel prices in the database
def update_hotel_prices(hotel_name: str, price: float):
    cursor.execute('''
        INSERT INTO hotel_prices (hotel_name, price, timestamp)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (hotel_name, price))
    conn.commit()

# Define a function to monitor hotel prices and alert users
def monitor_hotel_prices(background_tasks: BackgroundTasks):
    # Fetch hotel prices from the database
    cursor.execute('SELECT hotel_name, price FROM hotel_prices ORDER BY timestamp DESC')
    hotel_prices = cursor.fetchall()

    # Check if prices have dropped or if preferred hotels are available
    for hotel_name, price in hotel_prices:
        # Simulate checking if prices have dropped or if preferred hotels are available
        if price < 200.0:
            # Alert users
            print(f'Price drop alert: {hotel_name} is now ${price:.2f}')

    # Schedule the next monitoring task
    background_tasks.add_task(monitor_hotel_prices, background_tasks)

# Define a route to trigger hotel price monitoring
@app.post('/monitor_hotel_prices')
async def trigger_monitoring(background_tasks: BackgroundTasks):
    background_tasks.add_task(monitor_hotel_prices, background_tasks)
    return JSONResponse({'message': 'Hotel price monitoring triggered'}, status_code=200)

# Define a route to fetch hotel prices
@app.get('/hotel_prices')
async def fetch_prices():
    cursor.execute('SELECT hotel_name, price FROM hotel_prices ORDER BY timestamp DESC')
    hotel_prices = cursor.fetchall()
    return JSONResponse({'hotel_prices': hotel_prices}, status_code=200)
