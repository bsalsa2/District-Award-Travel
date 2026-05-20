"""
Intake form router.
Optimized for high-throughput form submissions with proper validation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Local imports
from ...api import schemas, models, database

router = APIRouter()

@router.post("/intake", response_model=schemas.IntakeResponse, status_code=status.HTTP_201_CREATED)
async def create_intake(intake: schemas.IntakeCreate, db: Session = Depends(database.get_db)):
    """
    Create a new intake from form submission.
    Optimized for minimal database operations with proper relationships.
    """
    # Check if client exists, create if not
    db_client = db.query(models.Client).filter(
        models.Client.email == intake.email
    ).first()

    if not db_client:
        # Create new client
        db_client = models.Client(
            first_name=intake.first_name,
            last_name=intake.last_name,
            email=intake.email,
            phone=intake.phone
        )
        db.add(db_client)
        db.commit()
        db.refresh(db_client)

    # Create intake record linked to client
    db_intake = models.Intake(
        client_id=db_client.id,
        first_name=intake.first_name,
        last_name=intake.last_name,
        email=intake.email,
        phone=intake.phone,
        travel_date=intake.travel_date,
        destination=intake.destination,
        budget=intake.budget,
        notes=intake.notes,
        status="pending"
    )

    db.add(db_intake)
    db.commit()
    db.refresh(db_intake)

    return db_intake

@router.get("/intakes", response_model=List[schemas.IntakeResponse])
async def read_intakes(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """
    Get all intakes with pagination.
    Optimized for large datasets with proper indexing.
    """
    intakes = db.query(models.Intake).offset(skip).limit(limit).all()
    return intakes

@router.get("/intakes/{intake_id}", response_model=schemas.IntakeResponse)
async def read_intake(intake_id: int, db: Session = Depends(database.get_db)):
    """
    Get a specific intake by ID.
    Optimized for fast lookups with primary key index.
    """
    intake = db.query(models.Intake).filter(models.Intake.id == intake_id).first()
    if intake is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intake not found"
        )
    return intake

@router.get("/clients/{client_id}/intakes", response_model=List[schemas.IntakeResponse])
async def read_client_intakes(client_id: int, db: Session = Depends(database.get_db)):
    """
    Get all intakes for a specific client.
    Optimized with client_id index.
    """
    intakes = db.query(models.Intake).filter(
        models.Intake.client_id == client_id
    ).all()
    return intakes
