"""
Client management router for District Award Travel API.
Handles client profiles and client data operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from .. import database
from ..auth import get_current_active_user

router = APIRouter(
    prefix="/clients",
    tags=["clients"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=dict)
async def create_client(
    client_data: database.Client.__table__.c,
    current_user: database.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Create new client profile."""
    db_client = database.Client(
        user_id=current_user.id,
        first_name=client_data.first_name,
        last_name=client_data.last_name,
        phone=client_data.phone,
        email=client_data.email,
        frequent_flyer_number=client_data.frequent_flyer_number,
        airline_preferences=client_data.airline_preferences,
        cabin_preferences=client_data.cabin_preferences,
        loyalty_programs=client_data.loyalty_programs,
        notes=client_data.notes
    )

    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    return {
        "message": "Client profile created successfully",
        "client_id": db_client.id
    }

@router.get("/", response_model=List[dict])
async def list_clients(
    current_user: database.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """List all client profiles for current user."""
    clients = db.query(database.Client).filter(
        database.Client.user_id == current_user.id
    ).all()

    return [{
        "id": client.id,
        "first_name": client.first_name,
        "last_name": client.last_name,
        "email": client.email,
        "phone": client.phone,
        "frequent_flyer_number": client.frequent_flyer_number,
        "airline_preferences": client.airline_preferences,
        "cabin_preferences": client.cabin_preferences,
        "loyalty_programs": client.loyalty_programs,
        "notes": client.notes,
        "created_at": client.created_at,
        "updated_at": client.updated_at
    } for client in clients]
