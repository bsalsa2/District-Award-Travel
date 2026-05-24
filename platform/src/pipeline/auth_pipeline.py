import sqlite3
from fastapi import FastAPI, Depends
from platform.src.intelligence.auth import get_current_user

app = FastAPI()

def get_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    return conn, cursor

@app.get("/users")
async def read_users(current_user: str = Depends(get_current_user)):
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM users WHERE username = ?", (current_user,))
    user = cursor.fetchone()
    conn.close()
    return {"username": user[0], "email": user[1], "full_name": user[2]}
