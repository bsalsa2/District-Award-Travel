import sqlite3
import numpy as np

class Pipeline:
    def __init__(self):
        self.conn = sqlite3.connect("award_flights.db")
        self.cursor = self.conn.cursor()

    def book_award_flight(self, user):
        # Book the award flight
        self.cursor.execute("INSERT INTO award_flights (user_id, flight_number) VALUES (?, ?)", (user.id, "AA123"))
        self.conn.commit()

    def cancel_award_flight(self, user):
        # Cancel the award flight
        self.cursor.execute("DELETE FROM award_flights WHERE user_id = ? AND flight_number = ?", (user.id, "AA123"))
        self.conn.commit()

    def run_pipeline(self, user):
        # Run the pipeline
        self.book_award_flight(user)
        self.cancel_award_flight(user)
