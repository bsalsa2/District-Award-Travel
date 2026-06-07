import sqlite3
import numpy as np

def get_bookings():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT date, COUNT(*) as count FROM bookings GROUP BY date ORDER BY date")
    bookings = c.fetchall()
    conn.close()
    return [{"date": booking[0], "count": booking[1]} for booking in bookings]
