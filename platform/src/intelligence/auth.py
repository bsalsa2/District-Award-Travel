import sqlite3
from sqlite3 import Error
import hashlib

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect("platform/src/intelligence/database.db")
        return conn
    except Error as e:
        print(e)

def create_table(conn):
    sql_create_table = """CREATE TABLE IF NOT EXISTS users (
                                username text PRIMARY KEY,
                                email text NOT NULL,
                                password text NOT NULL
                            );"""
    try:
        c = conn.cursor()
        c.execute(sql_create_table)
    except Error as e:
        print(e)

def authenticate_user(username, password):
    conn = create_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        if user and user[2] == hashlib.sha256(password.encode()).hexdigest():
            return {"username": user[0], "email": user[1]}
        else:
            return None

def get_user(token):
    conn = create_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (token,))
        user = cur.fetchone()
        if user:
            return {"username": user[0], "email": user[1]}
        else:
            return None

def register_user(username, email, password):
    conn = create_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users VALUES (?, ?, ?)", (username, email, hashlib.sha256(password.encode()).hexdigest()))
        conn.commit()

# Initialize database
conn = create_connection()
create_table(conn)
conn.close()

# Example usage
register_user("jeff", "jeff@example.com", "password123")
