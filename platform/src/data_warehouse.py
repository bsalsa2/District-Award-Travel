import sqlite3
import json
from typing import Dict, List

class DataWarehouse:
    def __init__(self):
        self.conn = sqlite3.connect("data_warehouse.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS award_travel_insights (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                flight_id INTEGER,
                award_type TEXT,
                travel_date TEXT,
                insights TEXT
            )
        """)
        self.conn.commit()

    def get_insights(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM award_travel_insights")
        rows = self.cursor.fetchall()
        insights = []
        for row in rows:
            insights.append({
                "id": row[0],
                "user_id": row[1],
                "flight_id": row[2],
                "award_type": row[3],
                "travel_date": row[4],
                "insights": row[5]
            })
        return insights

    def insert_insights(self, insights: Dict):
        self.cursor.execute("""
            INSERT INTO award_travel_insights (user_id, flight_id, award_type, travel_date, insights)
            VALUES (?, ?, ?, ?, ?)
        """, (insights["user_id"], insights["flight_id"], insights["award_type"], insights["travel_date"], insights["insights"]))
        self.conn.commit()
