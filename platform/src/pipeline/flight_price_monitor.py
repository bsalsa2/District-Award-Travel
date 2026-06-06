import sqlite3
import numpy as np
from fastapi import FastAPI, BackgroundTasks
from typing import List
from platform.src.intelligence.flight_price_model import FlightPriceModel

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('district_award_travel.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS flight_prices (
        id INTEGER PRIMARY KEY,
        flight_number TEXT,
        departure_airport TEXT,
        arrival_airport TEXT,
        price REAL,
        timestamp TEXT
    )
''')

# Define a function to fetch flight prices from the database
def fetch_flight_prices(flight_number: str, departure_airport: str, arrival_airport: str):
    cursor.execute('''
        SELECT price, timestamp
        FROM flight_prices
        WHERE flight_number = ? AND departure_airport = ? AND arrival_airport = ?
    ''', (flight_number, departure_airport, arrival_airport))
    return cursor.fetchall()

# Define a function to update flight prices in the database
def update_flight_price(flight_number: str, departure_airport: str, arrival_airport: str, price: float):
    cursor.execute('''
        INSERT INTO flight_prices (flight_number, departure_airport, arrival_airport, price, timestamp)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (flight_number, departure_airport, arrival_airport, price))
    conn.commit()

# Define a function to monitor flight prices
def monitor_flight_prices(flight_number: str, departure_airport: str, arrival_airport: str, target_price: float):
    prices = fetch_flight_prices(flight_number, departure_airport, arrival_airport)
    if prices:
        latest_price = prices[-1][0]
        if latest_price <= target_price:
            # Send alert to user
            print(f'Flight {flight_number} from {departure_airport} to {arrival_airport} is now available at ${latest_price}')
        else:
            # Update flight price model
            model = FlightPriceModel()
            model.update_price(flight_number, departure_airport, arrival_airport, latest_price)
    else:
        # Initialize flight price model
        model = FlightPriceModel()
        model.init_price(flight_number, departure_airport, arrival_airport)

# Define a background task to monitor flight prices
def background_monitor_flight_prices(flight_number: str, departure_airport: str, arrival_airport: str, target_price: float):
    while True:
        monitor_flight_prices(flight_number, departure_airport, arrival_airport, target_price)
        # Sleep for 1 minute
        import time
        time.sleep(60)

# Define an API endpoint to start monitoring flight prices
@app.post('/start_monitoring')
async def start_monitoring(flight_number: str, departure_airport: str, arrival_airport: str, target_price: float):
    background_tasks = BackgroundTasks()
    background_tasks.add_task(background_monitor_flight_prices, flight_number, departure_airport, arrival_airport, target_price)
    return {'message': 'Monitoring started'}
