import sqlite3
from typing import List, Dict

class AvailabilityDB:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER PRIMARY KEY,
                airline TEXT,
                origin TEXT,
                destination TEXT,
                date TEXT,
                cabin TEXT,
                miles_required INTEGER,
                taxes_usd REAL,
                available_seats INTEGER,
                program_name TEXT
            )
        """)
        self.conn.commit()

    def insert_availability(self, data: Dict):
        self.cursor.execute("""
            INSERT INTO availability (airline, origin, destination, date, cabin, miles_required, taxes_usd, available_seats, program_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['airline'],
            data['origin'],
            data['destination'],
            data['date'],
            data['cabin'],
            data['miles_required'],
            data['taxes_usd'],
            data['available_seats'],
            data['program_name']
        ))
        self.conn.commit()

    def get_last_searches(self, limit: int = 50):
        self.cursor.execute("""
            SELECT * FROM availability
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()
