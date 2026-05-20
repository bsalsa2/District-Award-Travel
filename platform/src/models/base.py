from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON
from sqlalchemy.sql import func

Base = declarative_base()

class PredictiveModel(Base):
    __tablename__ = "predictive_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    version = Column(String(50))
    description = Column(String(1000))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PredictionCache(Base):
    __tablename__ = "prediction_cache"

    id = Column(Integer, primary_key=True, index=True)
    route_key = Column(String(100), index=True)
    departure_date = Column(Date, index=True)
    prediction = Column(JSON)
    confidence = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), index=True)

class PredictiveHold(Base):
    __tablename__ = "predictive_holds"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    route_key = Column(String(100), index=True)
    departure_date = Column(Date, index=True)
    hold_token = Column(String(64), unique=True, index=True)
    expiry = Column(DateTime(timezone=True), index=True)
    status = Column(String(20), default="active")
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
