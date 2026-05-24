from fastapi import FastAPI
from pydantic import BaseModel
from platform.src.intelligence.award_travel_model import AwardTravelModel

app = FastAPI()

class TripRequest(BaseModel):
    destination: str
    departure_date: str
    return_date: str

@app.post("/plan-trip")
async def plan_trip(trip_request: TripRequest):
    award_travel_model = AwardTravelModel()
    # Load data and train model
    # For demonstration purposes, assume we have a trained model
    award_travel_model.train(np.array([[1, 2], [3, 4]]), np.array([5, 6]))

    # Predict award travel prices
    prediction = award_travel_model.predict(np.array([[7, 8]]))

    return {"prediction": prediction}
