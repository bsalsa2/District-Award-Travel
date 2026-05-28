import numpy as np
from sqlite3 import connect

class AwardTravelBookingSystem:
    def __init__(self):
        self.conn = connect("award_travel.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS award_travel_bookings
            (id INTEGER PRIMARY KEY, origin TEXT, destination TEXT, travel_date TEXT)
        """)
        self.conn.commit()

    def book_award_travel(self, origin: str, destination: str, travel_date: str):
        self.cursor.execute("""
            INSERT INTO award_travel_bookings (origin, destination, travel_date)
            VALUES (?, ?, ?)
        """, (origin, destination, travel_date))
        self.conn.commit()

    def get_award_travel_bookings(self):
        self.cursor.execute("SELECT * FROM award_travel_bookings")
        return self.cursor.fetchall()

