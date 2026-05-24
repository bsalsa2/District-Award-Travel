import sqlite3
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

# Define the award points redemption model
class AwardPointsRedemption(BaseModel):
    user_id: str
    award_points: int
    redemption_date: str

# Define the database connection
conn = sqlite3.connect("award_points.db")
cursor = conn.cursor()

# Create the award points redemption table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS award_points_redemption (
        id INTEGER PRIMARY KEY,
        user_id TEXT,
        award_points INTEGER,
        redemption_date TEXT
    );
""")

# Define the award points redemption endpoint
@app.post("/award_points_redemption")
async def create_award_points_redemption(award_points_redemption: AwardPointsRedemption):
    cursor.execute("""
        INSERT INTO award_points_redemption (user_id, award_points, redemption_date)
        VALUES (?, ?, ?);
    """, (award_points_redemption.user_id, award_points_redemption.award_points, award_points_redemption.redemption_date))
    conn.commit()
    return {"message": "Award points redemption created successfully"}

# Define the award points redemption retrieval endpoint
@app.get("/award_points_redemption")
async def read_award_points_redemption(user_id: str):
    cursor.execute("""
        SELECT * FROM award_points_redemption
        WHERE user_id = ?;
    """, (user_id,))
    award_points_redemptions = cursor.fetchall()
    return award_points_redemptions
