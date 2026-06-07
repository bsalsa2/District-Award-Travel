import sqlite3
import numpy as np

def get_cancellations():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT date, COUNT(*) as count FROM cancellations GROUP BY date ORDER BY date")
    cancellations = c.fetchall()
    conn.close()
    return [{"date": cancellation[0], "count": cancellation[1]} for cancellation in cancellations]
