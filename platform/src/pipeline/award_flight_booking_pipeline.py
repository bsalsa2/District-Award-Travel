import sqlite3
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

# Connect to SQLite database
conn = sqlite3.connect('award_flight_booking.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS award_flight_bookings
    (id INTEGER PRIMARY KEY, 
     booking_date DATE, 
     revenue REAL, 
     customer_demographics TEXT)
''')

# Insert sample data
sample_data = [
    ('2022-01-01', 1000.0, 'Male, 25-34'),
    ('2022-01-02', 1200.0, 'Female, 35-44'),
    ('2022-01-03', 1500.0, 'Male, 45-54'),
    ('2022-01-04', 1800.0, 'Female, 55-64'),
    ('2022-01-05', 2000.0, 'Male, 65+')
]
cursor.executemany('INSERT INTO award_flight_bookings (booking_date, revenue, customer_demographics) VALUES (?, ?, ?)', sample_data)
conn.commit()

# Define pipeline to extract analytics data
def extract_analytics_data():
    cursor.execute('SELECT * FROM award_flight_bookings')
    data = cursor.fetchall()
    return data

# Define pipeline to process analytics data
def process_analytics_data(data):
    booking_trends = []
    revenue = []
    customer_demographics = []
    for row in data:
        booking_trends.append(row[1])
        revenue.append(row[2])
        customer_demographics.append(row[3])
    return booking_trends, revenue, customer_demographics

# Define pipeline to load analytics data into dashboard
def load_analytics_data(booking_trends, revenue, customer_demographics):
    return {
        'booking_trends': booking_trends,
        'revenue': revenue,
        'customer_demographics': customer_demographics
    }

# Define API endpoint to retrieve analytics data
@app.get('/analytics')
async def get_analytics():
    data = extract_analytics_data()
    booking_trends, revenue, customer_demographics = process_analytics_data(data)
    analytics_data = load_analytics_data(booking_trends, revenue, customer_demographics)
    return JSONResponse(content=analytics_data, media_type='application/json')
