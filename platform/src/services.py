from platform.src.models import AwardSearchRequest, AwardSearchResult
from platform.src.repositories import AwardRepository
import asyncio

class AwardSearchService:
    def __init__(self):
        self.repository = AwardRepository()

    async def search_awards(self, request: AwardSearchRequest):
        results = await self.repository.search_awards(request)
        return results
