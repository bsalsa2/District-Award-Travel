"""
Database models and session management for District Award Travel.
Optimized for high-throughput award travel operations.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import os
from typing import Optional
import jwt
import hashlib
from passlib.context import CryptContext

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./district_award.db")
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    """User model for authentication and client management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    clients = relationship("Client", back_populates="user", cascade="all, delete-orphan")

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)

    def get_id(self) -> int:
        return self.id

class Client(Base):
    """Client profile model for award travel clients."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    frequent_flyer_number = Column(String(50))
    airline_preferences = Column(String(200))
    cabin_preferences = Column(String(100))
    loyalty_programs = Column(String(200))
    notes = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="clients")

class AwardProgram(Base):
    """Airline award program information."""
    __tablename__ = "award_programs"

    id = Column(Integer, primary_key=True, index=True)
    airline = Column(String(50), nullable=False)
    program_name = Column(String(100), nullable=False)
    alliance = Column(String(50))
    website = Column(String(255))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AwardSearch(Base):
    """Award search cache and history."""
    __tablename__ = "award_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    origin = Column(String(10), nullable=False)
    destination = Column(String(10), nullable=False)
    cabin_class = Column(String(20), nullable=False)
    departure_date = Column(String(20))
    return_date = Column(String(20))
    adults = Column(Integer, default=1)
    children = Column(Integer, default=0)
    infants = Column(Integer, default=0)
    results_count = Column(Integer, default=0)
    search_time = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))

class AwardResult(Base):
    """Cached award search results."""
    __tablename__ = "award_results"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("award_searches.id"))
    airline = Column(String(50), nullable=False)
    airline_code = Column(String(10))
    flight_number = Column(String(20))
    route = Column(String(50), nullable=False)
    origin = Column(String(10), nullable=False)
    destination = Column(String(10), nullable=False)
    cabin_class = Column(String(20), nullable=False)
    miles_required = Column(Integer, nullable=False)
    cash_value_usd = Column(Float, nullable=False)
    cpp = Column(Float, comment="Cents per point")  # miles_required / cash_value_usd * 100
    verdict = Column(String(20), nullable=False)  # EXCELLENT, GOOD, FAIR, SKIP
    departure_date = Column(String(20))
    return_date = Column(String(20))
    booking_url = Column(String(500))
    program_name = Column(String(100))
    alliance = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    search = relationship("AwardSearch", backref="results")

def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database with tables."""
    Base.metadata.create_all(bind=engine)

def hash_password(password: str) -> str:
    """Hash password for secure storage."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed version."""
    return pwd_context.verify(plain_password, hashed_password)
