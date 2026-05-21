import networkx as nx
import sqlite3

class GraphDatabase:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.conn = sqlite3.connect("awards.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS awards (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                points_required INTEGER
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                points_balance INTEGER
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_award_relationships (
                user_id INTEGER,
                award_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (award_id) REFERENCES awards (id)
            )
        """)
        self.conn.commit()

    def get_awards(self):
        self.cursor.execute("SELECT * FROM awards")
        awards = self.cursor.fetchall()
        return [{"id": award[0], "name": award[1], "description": award[2], "points_required": award[3]} for award in awards]

    def create_user(self, user):
        self.cursor.execute("INSERT INTO users (name, email, points_balance) VALUES (?, ?, ?)", (user.name, user.email, user.points_balance))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = self.cursor.fetchone()
        return {"id": user[0], "name": user[1], "email": user[2], "points_balance": user[3]}

    def get_user_award_relationships(self, user_id):
        self.cursor.execute("SELECT award_id FROM user_award_relationships WHERE user_id = ?", (user_id,))
        relationships = self.cursor.fetchall()
        return [relationship[0] for relationship in relationships]
