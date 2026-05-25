from fastapi import FastAPI, Request
from platform.src.pipeline.airline_api import AirlineAPI
from platform.src.intelligence.flight_recommender import FlightRecommender

app = FastAPI()

airline_api = AirlineAPI("YOUR_API_KEY")
flight_recommender = FlightRecommender(airline_api)

@app.post("/api/recommended-flights")
async def get_recommended_flights(request: Request):
    data = await request.json()
    origin = data["origin"]
    destination = data["destination"]
    departure_date = data["departure_date"]

    recommended_flights = flight_recommender.recommend_flights(origin, destination, departure_date)
    return recommended_flights
