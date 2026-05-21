from fastapi import FastAPI
from platform.src.database import GraphDatabaseClient
from platform.src.models import AirlineRoute, AwardAvailability, TransferBonus

app = FastAPI()

graph_db_client = GraphDatabaseClient("bolt://localhost:7687", auth=("neo4j", "password"))

@app.post("/airline_routes/")
def create_airline_route(airline_route: AirlineRoute):
    graph_db_client.create_airline_route(airline_route)
    return {"message": "Airline route created successfully"}

@app.post("/award_availability/")
def create_award_availability(award_availability: AwardAvailability):
    graph_db_client.create_award_availability(award_availability)
    return {"message": "Award availability created successfully"}

@app.post("/transfer_bonuses/")
def create_transfer_bonus(transfer_bonus: TransferBonus):
    graph_db_client.create_transfer_bonus(transfer_bonus)
    return {"message": "Transfer bonus created successfully"}

@app.get("/award_search/")
def award_search(origin: str, destination: str):
    result = graph_db_client.query_award_search(origin, destination)
    return {"result": result}
