import sqlite3
import numpy as np

def process_cancellations():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM cancellations")
    cancellations = c.fetchall()
    conn.close()
    return cancellations
