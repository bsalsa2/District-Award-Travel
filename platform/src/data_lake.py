import sqlite3
import json
from typing import Dict, List

class DataLake:
    def __init__(self):
        self.conn = sqlite3.connect("data_lake.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS award_travel_data (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                flight_id INTEGER,
                award_type TEXT,
                travel_date TEXT
            )
        """)
        self.conn.commit()

    def get_data(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM award_travel_data")
        rows = self.cursor.fetchall()
        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "user_id": row[1],
                "flight_id": row[2],
                "award_type": row[3],
                "travel_date": row[4]
            })
        return data

    def insert_data(self, data: Dict):
        self.cursor.execute("""
            INSERT INTO award_travel_data (user_id, flight_id, award_type, travel_date)
            VALUES (?, ?, ?, ?)
        """, (data["user_id"], data["flight_id"], data["award_type"], data["travel_date"]))
        self.conn.commit()
