import sqlite3
from typing import Dict

class AwardPointsModel:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS award_points (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def get_user_points(self, user_id: int) -> int:
        self.cursor.execute("SELECT points FROM award_points WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        if result is None:
            return 0
        return result[0]

    def update_user_points(self, user_id: int, points: int):
        self.cursor.execute("INSERT OR REPLACE INTO award_points (user_id, points) VALUES (?, ?)", (user_id, points))
        self.conn.commit()

    def close(self):
        self.conn.close()
