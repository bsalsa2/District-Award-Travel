from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List
from platform.src.database.clients_db import ClientsDB

app = FastAPI()
clients_db = ClientsDB()

class Client(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    created_at: str
    total_miles_managed: int
    programs: dict
    notes: str
    status: str

@app.post("/clients")
async def create_client(client: Client):
    client_id = clients_db.create_client(client)
    return JSONResponse(content={"id": client_id}, status_code=201)

@app.get("/clients")
async def get_all_clients():
    clients = clients_db.get_all_clients()
    return JSONResponse(content=clients, status_code=200)

@app.get("/clients/{id}")
async def get_client(id: int):
    client = clients_db.get_client(id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return JSONResponse(content=client, status_code=200)

@app.patch("/clients/{id}")
async def update_client(id: int, client: Client):
    clients_db.update_client(id, client)
    return JSONResponse(content={"message": "Client updated successfully"}, status_code=200)
