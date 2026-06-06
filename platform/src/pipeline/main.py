from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from award_travel_model import AwardTravelModel

app = FastAPI()

# Create an instance of the award travel model
award_travel_model = AwardTravelModel()

# Define a route for getting travel options
@app.get('/get_travel_options')
async def get_travel_options():
    return award_travel_model.get_travel_options()

# Define a route for getting a travel option
@app.get('/get_travel_option/{travel_option_id}')
async def get_travel_option(travel_option_id: int):
    return award_travel_model.get_travel_option(travel_option_id)
