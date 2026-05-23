import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Recommendation(BaseModel):
    destination: str
    airline: str

# Sample data for demonstration purposes
recommendations_data = [
    Recommendation(destination="New York", airline="American Airlines"),
    Recommendation(destination="Los Angeles", airline="Delta Air Lines"),
    Recommendation(destination="Chicago", airline="United Airlines"),
    Recommendation(destination="Houston", airline="Southwest Airlines"),
    Recommendation(destination="Phoenix", airline="American Airlines"),
]

@app.get("/recommendations")
async def get_recommendations(query: str = None):
    if query:
        # Filter recommendations based on query
        filtered_recommendations = [rec for rec in recommendations_data if query.lower() in rec.destination.lower() or query.lower() in rec.airline.lower()]
        return filtered_recommendations
    else:
        # Return all recommendations
        return recommendations_data
