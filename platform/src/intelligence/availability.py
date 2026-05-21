import sqlite3
from typing import Dict

class Availability:
    def __init__(self, db_path: str = "platform/src/pipeline/availability.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def check_availability(self, award_id: int) -> bool:
        self.cursor.execute("SELECT availability FROM awards WHERE id = ?", (award_id,))
        award_availability = self.cursor.fetchone()[0]
        return award_availability > 0

    def update_availability(self, award_id: int, availability: int) -> None:
        self.cursor.execute("UPDATE awards SET availability = availability + ? WHERE id = ?", (availability, award_id))
        self.conn.commit()

    def close_connection(self) -> None:
        self.conn.close()
