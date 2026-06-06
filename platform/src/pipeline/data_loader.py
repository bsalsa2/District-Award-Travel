import pandas as pd
import sqlite3

class DataLoader:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def load_data(self):
        query = 'SELECT * FROM award_travel_data'
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        columns = [description[0] for description in self.cursor.description]
        data = pd.DataFrame(rows, columns=columns)
        return data

    def close(self):
        self.conn.close()
