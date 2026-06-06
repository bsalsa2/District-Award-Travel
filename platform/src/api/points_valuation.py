from fastapi import APIRouter, HTTPException
from platform.src.services.valuation_service import ValuationService

router = APIRouter()
valuation_service = ValuationService('platform/src/data/points_values.csv')

@router.get("/valuations")
async def get_all_valuations():
    return valuation_service.get_all_valuations()

@router.get("/valuations/{program}")
async def get_valuation(program: str):
    valuation = valuation_service.get_valuation(program)
    if valuation == 0.0:
        raise HTTPException(status_code=404, detail="Program not found")
    return {'program': program, 'valuation': valuation}

@router.get("/valuations/{program}/{points}")
async def calculate_value(program: str, points: int):
    return valuation_service.calculate_value(program, points)
