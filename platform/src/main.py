from fastapi import FastAPI, Request
from platform.src.intelligence.award_redemption_simulator import AwardRedemptionSimulator
from platform.src.pipeline.award_redemption_pipeline import AwardRedemptionPipeline
import json

app = FastAPI()

@app.post("/simulate-redemption")
async def simulate_redemption(request: Request):
    data = await request.json()
    client_id = data['client_id']
    travel_dates = data['travel_dates']
    destination = data['destination']

    simulator = AwardRedemptionSimulator(client_id, travel_dates, destination)
    simulation_results = simulator.simulate_redemption()

    return simulation_results
