from fastapi import APIRouter, HTTPException
from platform.src.graph import Graph
from platform.src.nlp import NLP

router = APIRouter()

# Initialize the graph and NLP models
graph = Graph()
nlp = NLP()

# Define a route for searching award travel routes
@router.get("/search")
async def search(query: str):
    try:
        # Process the query using NLP
        processed_query = await nlp.process_query(query)
        
        # Search for routes using the graph
        routes = await graph.search_routes(processed_query)
        
        return {"routes": routes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Define a route for getting route details
@router.get("/route/{route_id}")
async def get_route(route_id: int):
    try:
        # Get the route details from the graph
        route = await graph.get_route(route_id)
        
        return {"route": route}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
