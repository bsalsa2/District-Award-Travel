from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from elasticsearch import Elasticsearch
from py2neo import Graph, Node, Relationship
from platform.src.search import SearchService
from platform.src.graph import GraphService

app = FastAPI()

origins = [
    "http://localhost:8000",
    "http://localhost:8001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch()
graph = Graph("bolt://localhost:7687", auth=("neo4j", "password"))

search_service = SearchService(es)
graph_service = GraphService(graph)

@app.get("/search")
async def search(query: str):
    results = search_service.search(query)
    return JSONResponse(content=results, media_type="application/json")

@app.get("/filter")
async def filter(query: str):
    results = search_service.filter(query)
    return JSONResponse(content=results, media_type="application/json")

@app.get("/availability")
async def availability(query: str):
    results = graph_service.get_availability(query)
    return JSONResponse(content=results, media_type="application/json")

@app.get("/pricing")
async def pricing(query: str):
    results = graph_service.get_pricing(query)
    return JSONResponse(content=results, media_type="application/json")
