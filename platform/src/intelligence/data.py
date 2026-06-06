import sqlite3
import numpy as np

def get_user_behavior():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_behavior")
    rows = cursor.fetchall()
    labels = [row[0] for row in rows]
    data = [row[1] for row in rows]
    return {"labels": labels, "data": data}

def get_award_travel_data():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM award_travel_data")
    rows = cursor.fetchall()
    labels = [row[0] for row in rows]
    data = [row[1] for row in rows]
    return {"labels": labels, "data": data}
