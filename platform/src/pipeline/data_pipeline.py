import sqlite3
import numpy as np

class DataPipeline:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                preference_vector TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS travel_options (
                travel_id INTEGER PRIMARY KEY,
                feature_vector TEXT
            )
        ''')
        self.conn.commit()

    def insert_user_preferences(self, user_id, preference_vector):
        self.cursor.execute('INSERT INTO user_preferences VALUES (?, ?)', (user_id, str(preference_vector)))
        self.conn.commit()

    def insert_travel_options(self, travel_id, feature_vector):
        self.cursor.execute('INSERT INTO travel_options VALUES (?, ?)', (travel_id, str(feature_vector)))
        self.conn.commit()

    def get_user_preferences(self):
        self.cursor.execute('SELECT * FROM user_preferences')
        return self.cursor.fetchall()

    def get_travel_options(self):
        self.cursor.execute('SELECT * FROM travel_options')
        return self.cursor.fetchall()

# Example usage:
pipeline = DataPipeline('data.db')
pipeline.create_tables()
pipeline.insert_user_preferences(0, [1, 2, 3])
pipeline.insert_travel_options(0, [1, 2, 3])
print(pipeline.get_user_preferences())
print(pipeline.get_travel_options())
