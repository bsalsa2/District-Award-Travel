from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Enable CORS
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

class Client(BaseModel):
    id: int
    name: str

class Pipeline(BaseModel):
    id: int
    name: str

class TransferBonus(BaseModel):
    id: int
    amount: float

# Mock data
clients = [
    Client(id=1, name="Client 1"),
    Client(id=2, name="Client 2"),
]

pipelines = [
    Pipeline(id=1, name="Pipeline 1"),
    Pipeline(id=2, name="Pipeline 2"),
]

transfer_bonuses = [
    TransferBonus(id=1, amount=100.0),
    TransferBonus(id=2, amount=200.0),
]

# Routes
@app.get("/clients")
async def get_clients():
    return [{"id": client.id, "name": client.name} for client in clients]

@app.post("/clients")
async def create_client(client: Client):
    clients.append(client)
    return {"id": client.id, "name": client.name}

@app.get("/pipeline")
async def get_pipelines():
    return [{"id": pipeline.id, "name": pipeline.name} for pipeline in pipelines]

@app.post("/pipeline/add")
async def add_pipeline(pipeline: Pipeline):
    pipelines.append(pipeline)
    return {"id": pipeline.id, "name": pipeline.name}

@app.get("/transfer-bonuses")
async def get_transfer_bonuses():
    return [{"id": bonus.id, "amount": bonus.amount} for bonus in transfer_bonuses]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
