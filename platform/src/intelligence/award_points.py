import sqlite3
from typing import Dict

class AwardPoints:
    def __init__(self, db_path: str = "platform/src/pipeline/award_points.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def check_points(self, user_id: int, points: int) -> bool:
        self.cursor.execute("SELECT points FROM users WHERE id = ?", (user_id,))
        user_points = self.cursor.fetchone()[0]
        return user_points >= points

    def update_points(self, user_id: int, points: int) -> None:
        self.cursor.execute("UPDATE users SET points = points + ? WHERE id = ?", (points, user_id))
        self.conn.commit()

    def close_connection(self) -> None:
        self.conn.close()
