import sqlite3
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Create a database connection
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Define the pipeline endpoint
@app.get("/pipeline")
async def pipeline():
    # Query the database for the users
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()

    # Process the users' data
    processed_users = []
    for user in users:
        processed_users.append({"id": user[0], "username": user[1]})

    # Return the processed users' data
    return JSONResponse(content=processed_users, media_type="application/json")
