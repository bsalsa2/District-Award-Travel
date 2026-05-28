import numpy as np
from sqlite3 import connect

class BookingPipeline:
    def __init__(self):
        self.conn = connect("booking_pipeline.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_pipeline
            (id INTEGER PRIMARY KEY, origin TEXT, destination TEXT, travel_date TEXT)
        """)
        self.conn.commit()

    def process_booking(self, origin: str, destination: str, travel_date: str):
        self.cursor.execute("""
            INSERT INTO booking_pipeline (origin, destination, travel_date)
            VALUES (?, ?, ?)
        """, (origin, destination, travel_date))
        self.conn.commit()

    def get_booking_pipeline(self):
        self.cursor.execute("SELECT * FROM booking_pipeline")
        return self.cursor.fetchall()

