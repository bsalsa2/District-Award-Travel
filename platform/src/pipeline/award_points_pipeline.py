import numpy as np
from fastapi import APIRouter, Depends
from platform.src.intelligence.award_points_redemption import calculate_award_points_balance

router = APIRouter()

def process_award_points_pipeline(user_id: int):
    balance = calculate_award_points_balance(user_id)
    # Simulate a pipeline process to update the user's award points balance
    return balance

@router.post("/process-award-points-pipeline")
async def process_award_points_pipeline_endpoint(user_id: int):
    balance = process_award_points_pipeline(user_id)
    return {"award_points_balance": balance}
