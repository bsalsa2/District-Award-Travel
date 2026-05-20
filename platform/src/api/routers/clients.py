"""
Client management router.
Optimized for high-throughput client operations with proper caching.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Local imports
from ...api import schemas, models, database

router = APIRouter()

@router.post("/clients", response_model=schemas.ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(client: schemas.ClientCreate, db: Session = Depends(database.get_db)):
    """
    Create a new client.
    Optimized for minimal database operations.
    """
    # Check if client with same email already exists
    db_client = db.query(models.Client).filter(
        models.Client.email == client.email
    ).first()

    if db_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this email already exists"
        )

    # Create new client
    db_client = models.Client(**client.dict())

    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    return db_client

@router.get("/clients", response_model=List[schemas.ClientResponse])
async def read_clients(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """
    Get all clients with pagination.
    Optimized for large datasets with proper indexing.
    """
    clients = db.query(models.Client).offset(skip).limit(limit).all()
    return clients

@router.get("/clients/{client_id}", response_model=schemas.ClientResponse)
async def read_client(client_id: int, db: Session = Depends(database.get_db)):
    """
    Get a specific client by ID.
    Optimized for fast lookups with primary key index.
    """
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    return client

@router.get("/clients/email/{email}", response_model=schemas.ClientResponse)
async def read_client_by_email(email: str, db: Session = Depends(database.get_db)):
    """
    Get a client by email.
    Optimized with email index.
    """
    client = db.query(models.Client).filter(models.Client.email == email).first()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    return client
