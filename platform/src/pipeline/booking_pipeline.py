import sqlite3

class BookingPipeline:
    def __init__(self):
        self.conn = sqlite3.connect("bookings.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                flight_number TEXT,
                passenger_name TEXT
            )
        """)
        self.conn.commit()
    
    def book_flight(self, flight_number, passenger_name):
        self.cursor.execute("""
            INSERT INTO bookings (flight_number, passenger_name)
            VALUES (?, ?)
        """, (flight_number, passenger_name))
        self.conn.commit()
        return True
