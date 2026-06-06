import sqlite3
import numpy as np

def get_travel_history():
    conn = sqlite3.connect('travel_history.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM travel_history")
    travel_history = cursor.fetchall()
    conn.close()
    return travel_history

def get_preferences():
    conn = sqlite3.connect('preferences.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM preferences")
    preferences = cursor.fetchall()
    conn.close()
    return preferences
