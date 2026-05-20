from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from typing import List
import asyncio
import redis
import json

# Initialize FastAPI app
app = FastAPI()

# Initialize SQLAlchemy async engine with SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///district-award-travel.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(class_=AsyncSession, bind=engine, expire_on_commit=False)

# Initialize Redis for caching
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Define SQLAlchemy base
Base = declarative_base()

# Define Client model
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

# Define Award model
class Award(Base):
    __tablename__ = "awards"
    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    cabin = Column(String)
    price = Column(Integer)

# Create all tables in the engine
async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Dependency to get database session
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Route to get all clients
@app.get("/clients")
async def get_clients(db: AsyncSession = Depends(get_db)):
    clients = await db.query(Client).all()
    return [{"id": client.id, "name": client.name, "email": client.email} for client in clients]

# Route to create a new client
@app.post("/clients")
async def create_client(client: dict, db: AsyncSession = Depends(get_db)):
    new_client = Client(name=client["name"], email=client["email"])
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return {"id": new_client.id, "name": new_client.name, "email": new_client.email}

# Route to search for awards
@app.get("/awards/search")
async def search_awards(origin: str, destination: str, cabin: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"awards:{origin}:{destination}:{cabin}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)

    awards = await db.query(Award).filter(Award.origin == origin, Award.destination == destination, Award.cabin == cabin).all()
    result = [{"id": award.id, "origin": award.origin, "destination": award.destination, "cabin": award.cabin, "price": award.price} for award in awards]
    redis_client.set(cache_key, json.dumps(result))
    return result

# Route to get transfer bonuses
@app.get("/transfer-bonuses")
async def get_transfer_bonuses(db: AsyncSession = Depends(get_db)):
    # For now, just return a hardcoded list
    return [{"id": 1, "bonus": 1000}, {"id": 2, "bonus": 500}]

# Initialize models when the app starts
@app.on_event("startup")
async def startup_event():
    await init_models()

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
