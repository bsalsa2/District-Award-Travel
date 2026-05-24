from fastapi import APIRouter
from platform.src.services import AwardTravelService

award_travel_router = APIRouter()

@award_travel_router.get("/award-travel/search")
async def search_award_travel(query: str):
    results = await AwardTravelService.search_award_travel(query)
    return results
