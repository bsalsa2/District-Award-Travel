from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from platform.src.intelligence.recommender import get_recommendations

app = FastAPI()

@app.post("/recommend")
async def recommend(request: Request):
    data = await request.json()
    miles_balances = data["miles_balances"]
    travel_goals = data["travel_goals"]
    flexible_dates = data["flexible_dates"]
    recommendations = get_recommendations(miles_balances, travel_goals, flexible_dates)
    return JSONResponse(content={"recommendations": recommendations}, media_type="application/json")
