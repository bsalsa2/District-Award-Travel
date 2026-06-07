import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Flight(BaseModel):
    id: int
    departure: str
    arrival: str
    date: str
    award_value: float

class AwardFlightSearch:
    def __init__(self):
        self.conn = sqlite3.connect("award_flights.db")
        self.cursor = self.conn.cursor()

    def search(self, departure, arrival, date):
        self.cursor.execute("SELECT * FROM award_flights WHERE departure = ? AND arrival = ? AND date = ?", (departure, arrival, date))
        rows = self.cursor.fetchall()
        return [Flight(id=row[0], departure=row[1], arrival=row[2], date=row[3], award_value=row[4]) for row in rows]

# Example usage:
# search = AwardFlightSearch()
# flights = search.search("JFK", "LAX", "2026-06-07")
# for flight in flights:
#     print(flight)
