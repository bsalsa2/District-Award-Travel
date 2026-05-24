import sqlite3
from platform.src.models.user import User

class Database:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                preferences TEXT
            )
        """)
        self.conn.commit()

    def insert_user(self, user: User):
        self.cursor.execute("""
            INSERT INTO users (name, email, password, preferences)
            VALUES (?, ?, ?, ?)
        """, (user.name, user.email, user.password, str(user.preferences)))
        self.conn.commit()

    def get_user(self, user_id: int):
        self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_data = self.cursor.fetchone()
        if user_data:
            return User(id=user_data[0], name=user_data[1], email=user_data[2], password=user_data[3], preferences=user_data[4])
        return None

    def update_user(self, user: User):
        self.cursor.execute("""
            UPDATE users
            SET name = ?, email = ?, password = ?, preferences = ?
            WHERE id = ?
        """, (user.name, user.email, user.password, str(user.preferences), user.id))
        self.conn.commit()

    def delete_user(self, user_id: int):
        self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
