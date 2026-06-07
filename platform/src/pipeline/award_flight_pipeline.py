import sqlite3
import numpy as np

class AwardFlightPipeline:
    def __init__(self):
        self.conn = sqlite3.connect('award_flights.db')
        self.cursor = self.conn.cursor()

    def search_flights(self, search_request):
        origin = search_request['origin']
        destination = search_request['destination']
        departure_date = search_request['departureDate']
        return_date = search_request['returnDate']
        class_type = search_request['class']

        self.cursor.execute('''
            SELECT * FROM award_flights
            WHERE origin = ? AND destination = ? AND departure_date = ? AND return_date = ? AND class = ?
        ''', (origin, destination, departure_date, return_date, class_type))

        results = self.cursor.fetchall()
        return results
