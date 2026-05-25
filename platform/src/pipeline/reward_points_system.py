from typing import Dict
import sqlite3
import numpy as np

class RewardPointsSystem:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reward_points
            (id INTEGER PRIMARY KEY, user_id INTEGER, points INTEGER, created_at TEXT)
        ''')
        self.conn.commit()

    def earn_points(self, user_id: int, points: int):
        self.cursor.execute('INSERT INTO reward_points (user_id, points, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (user_id, points))
        self.conn.commit()

    def redeem_points(self, user_id: int, points: int):
        self.cursor.execute('SELECT * FROM reward_points WHERE user_id = ?', (user_id,))
        user_points = self.cursor.fetchall()
        total_points = sum([point[2] for point in user_points])
        if total_points >= points:
            self.cursor.execute('DELETE FROM reward_points WHERE user_id = ? AND points = ?', (user_id, points))
            self.conn.commit()
            return True
        return False

    def get_user_points(self, user_id: int):
        self.cursor.execute('SELECT * FROM reward_points WHERE user_id = ?', (user_id,))
        user_points = self.cursor.fetchall()
        return sum([point[2] for point in user_points])

    def close_connection(self):
        self.conn.close()
