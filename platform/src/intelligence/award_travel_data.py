import numpy as np
import sqlite3

# Connect to the database
conn = sqlite3.connect('award_travel_data.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS award_travel_data
    (month TEXT, value REAL)
''')

# Insert sample data
sample_data = [
    ('January', 100),
    ('February', 120),
    ('March', 150),
    ('April', 180),
    ('May', 200),
    ('June', 220)
]
cursor.executemany('INSERT INTO award_travel_data VALUES (?, ?)', sample_data)

# Commit changes and close connection
conn.commit()
conn.close()
