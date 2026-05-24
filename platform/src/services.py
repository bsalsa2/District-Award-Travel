import asyncio
from platform.src.models import AwardTravelRoute
from platform.src.repositories import AwardTravelRepository
from platform.src.utils import KnowledgeGraph

class AwardTravelService:
    def __init__(self):
        self.repository = AwardTravelRepository()
        self.knowledge_graph = KnowledgeGraph()

    async def initialize(self):
        await self.repository.initialize()

    async def shutdown(self):
        await self.repository.shutdown()

    async def search_award_travel(self, query: str):
        entities = self.knowledge_graph.disambiguate_entities(query)
        routes = await self.repository.search_award_travel(entities)
        return routes
