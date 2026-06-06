from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi import Depends
from sqlalchemy import create_engine, Column, Integer, String, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import Optional

# Define the database connection
engine = create_engine('sqlite:///redemptions.db')
Base = declarative_base()

# Define the Redemption model
class Redemption(Base):
    __tablename__ = 'redemptions'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, nullable=False)
    award_id = Column(Integer, nullable=False)
    redemption_date = Column(Date, nullable=False)
    booking_id = Column(Integer)
    status = Column(String, nullable=False)

# Create the database tables
Base.metadata.create_all(engine)

# Create a session maker
SessionLocal = sessionmaker(bind=engine)

# Define the Redemption request model
class RedemptionRequest(BaseModel):
    client_id: int
    award_id: int
    redemption_date: str
    booking_id: Optional[int]

# Define the Redemption response model
class RedemptionResponse(BaseModel):
    id: int
    client_id: int
    award_id: int
    redemption_date: str
    booking_id: Optional[int]
    status: str

# Create a FastAPI app
app = FastAPI()

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a new redemption
@app.post("/redemptions", response_model=RedemptionResponse)
def create_redemption(redemption: RedemptionRequest, db: Session = Depends(get_db)):
    new_redemption = Redemption(
        client_id=redemption.client_id,
        award_id=redemption.award_id,
        redemption_date=redemption.redemption_date,
        booking_id=redemption.booking_id,
        status='pending'
    )
    db.add(new_redemption)
    db.commit()
    db.refresh(new_redemption)
    return RedemptionResponse(
        id=new_redemption.id,
        client_id=new_redemption.client_id,
        award_id=new_redemption.award_id,
        redemption_date=new_redemption.redemption_date,
        booking_id=new_redemption.booking_id,
        status=new_redemption.status
    )

# Get all redemptions
@app.get("/redemptions", response_model=list[RedemptionResponse])
def get_redemptions(db: Session = Depends(get_db)):
    redemptions = db.query(Redemption).all()
    return [
        RedemptionResponse(
            id=redemption.id,
            client_id=redemption.client_id,
            award_id=redemption.award_id,
            redemption_date=redemption.redemption_date,
            booking_id=redemption.booking_id,
            status=redemption.status
        ) for redemption in redemptions
    ]

# Get a redemption by ID
@app.get("/redemptions/{redemption_id}", response_model=RedemptionResponse)
def get_redemption(redemption_id: int, db: Session = Depends(get_db)):
    redemption = db.query(Redemption).filter(Redemption.id == redemption_id).first()
    if redemption is None:
        raise HTTPException(status_code=404, detail="Redemption not found")
    return RedemptionResponse(
        id=redemption.id,
        client_id=redemption.client_id,
        award_id=redemption.award_id,
        redemption_date=redemption.redemption_date,
        booking_id=redemption.booking_id,
        status=redemption.status
    )

# Update a redemption
@app.put("/redemptions/{redemption_id}", response_model=RedemptionResponse)
def update_redemption(redemption_id: int, redemption: RedemptionRequest, db: Session = Depends(get_db)):
    existing_redemption = db.query(Redemption).filter(Redemption.id == redemption_id).first()
    if existing_redemption is None:
        raise HTTPException(status_code=404, detail="Redemption not found")
    existing_redemption.client_id = redemption.client_id
    existing_redemption.award_id = redemption.award_id
    existing_redemption.redemption_date = redemption.redemption_date
    existing_redemption.booking_id = redemption.booking_id
    db.commit()
    db.refresh(existing_redemption)
    return RedemptionResponse(
        id=existing_redemption.id,
        client_id=existing_redemption.client_id,
        award_id=existing_redemption.award_id,
        redemption_date=existing_redemption.redemption_date,
        booking_id=existing_redemption.booking_id,
        status=existing_redemption.status
    )

# Delete a redemption
@app.delete("/redemptions/{redemption_id}")
def delete_redemption(redemption_id: int, db: Session = Depends(get_db)):
    redemption = db.query(Redemption).filter(Redemption.id == redemption_id).first()
    if redemption is None:
        raise HTTPException(status_code=404, detail="Redemption not found")
    db.delete(redemption)
    db.commit()
    return JSONResponse(content={"message": "Redemption deleted"}, status_code=200)
