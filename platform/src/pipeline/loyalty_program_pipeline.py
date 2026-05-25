import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

class LoyaltyProgramPipeline:
    def __init__(self):
        self.loyalty_program_data = {}

    def update_loyalty_program(self, loyalty_program_data: Dict):
        self.loyalty_program_data = loyalty_program_data

    def get_loyalty_program_data(self) -> Dict:
        return self.loyalty_program_data

@app.get("/loyalty_program")
def get_loyalty_program():
    pipeline = LoyaltyProgramPipeline()
    pipeline.update_loyalty_program({"flights": [{"airline": "AA", "destination": "LAX", "travel_date": "2026-06-01"}, {"airline": "UA", "destination": "JFK", "travel_date": "2026-06-15"}]})
    loyalty_program_data = pipeline.get_loyalty_program_data()
    return JSONResponse(content=loyalty_program_data, media_type="application/json")
