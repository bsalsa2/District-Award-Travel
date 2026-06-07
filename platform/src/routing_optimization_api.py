from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from typing import List
import networkx as nx
import asyncio

# Define the database connection
engine = create_engine('sqlite:///award_flights.db')
Session = sessionmaker(bind=engine)
Base = declarative_base()

# Define the AwardFlight model
class AwardFlight(Base):
    __tablename__ = 'award_flights'
    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    airline = Column(String)
    award_availability = Column(Integer)

# Create the database tables
Base.metadata.create_all(engine)

# Define the FastAPI app
app = FastAPI()

# Define the routing optimization endpoint
@app.post("/optimize_route")
async def optimize_route(origin: str, destination: str, preferences: List[str]):
    # Create a graph to represent the award flights
    G = nx.DiGraph()
    
    # Query the database for award flights
    session = Session()
    award_flights = session.query(AwardFlight).all()
    
    # Add edges to the graph for each award flight
    for flight in award_flights:
        G.add_edge(flight.origin, flight.destination, airline=flight.airline, award_availability=flight.award_availability)
    
    # Use Dijkstra's algorithm to find the shortest path
    try:
        path = nx.shortest_path(G, origin, destination, weight='award_availability')
    except nx.NetworkXNoPath:
        return JSONResponse(content={"error": "No path found"}, status_code=404)
    
    # Filter the path based on client preferences
    filtered_path = []
    for i in range(len(path) - 1):
        edge = G.get_edge_data(path[i], path[i+1])
        if edge['airline'] in preferences:
            filtered_path.append((path[i], path[i+1], edge['airline']))
    
    # Return the optimized route
    return JSONResponse(content={"route": filtered_path}, status_code=200)

# Define the Award Flight Booking Search Functionality
@app.post("/search_flights")
async def search_flights(origin: str, destination: str, preferences: List[str]):
    # Query the database for award flights
    session = Session()
    award_flights = session.query(AwardFlight).all()
    
    # Filter the award flights based on client preferences
    filtered_flights = []
    for flight in award_flights:
        if flight.origin == origin and flight.destination == destination and flight.airline in preferences:
            filtered_flights.append(flight)
    
    # Return the filtered award flights
    return JSONResponse(content={"flights": [{"origin": flight.origin, "destination": flight.destination, "airline": flight.airline} for flight in filtered_flights]}, status_code=200)
