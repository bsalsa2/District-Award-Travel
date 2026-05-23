import sqlite3

class Database:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def create_tables(self):
        query = """
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                preferences TEXT
            )
        """
        self.cursor.execute(query)
        query = """
            CREATE TABLE IF NOT EXISTS travel_history (
                travel_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                destination TEXT,
                travel_date TEXT,
                FOREIGN KEY (user_id) REFERENCES user_data (user_id)
            )
        """
        self.cursor.execute(query)
        self.conn.commit()

    def insert_user_data(self, user_id, name, email, preferences):
        query = "INSERT INTO user_data VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (user_id, name, email, preferences))
        self.conn.commit()

    def insert_travel_history(self, travel_id, user_id, destination, travel_date):
        query = "INSERT INTO travel_history VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (travel_id, user_id, destination, travel_date))
        self.conn.commit()
