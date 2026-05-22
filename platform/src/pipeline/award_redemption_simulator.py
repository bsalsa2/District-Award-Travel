import numpy as np
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from platform.src.intelligence.client_profile import ClientProfile
from platform.src.intelligence.award_redemption_model import AwardRedemptionModel

app = FastAPI()

def get_client_profile(client_id: int):
    return ClientProfile(client_id)

def get_award_redemption_model():
    return AwardRedemptionModel()

@app.post("/simulate_award_redemption")
async def simulate_award_redemption(request: Request, client_id: int = Depends(get_client_profile)):
    client_profile = get_client_profile(client_id)
    award_redemption_model = get_award_redemption_model()
    simulation_results = award_redemption_model.simulate_award_redemption(client_profile)
    return JSONResponse(content=simulation_results, media_type="application/json")

@app.post("/save_simulation_results")
async def save_simulation_results(request: Request, client_id: int = Depends(get_client_profile), simulation_results: dict = Depends()):
    client_profile = get_client_profile(client_id)
    client_profile.save_simulation_results(simulation_results)
    return JSONResponse(content={"message": "Simulation results saved successfully"}, media_type="application/json")

@app.get("/get_simulation_results")
async def get_simulation_results(request: Request, client_id: int = Depends(get_client_profile)):
    client_profile = get_client_profile(client_id)
    simulation_results = client_profile.get_simulation_results()
    return JSONResponse(content=simulation_results, media_type="application/json")
