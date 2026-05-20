"""
SQLAlchemy models for District Award Travel.
Optimized for high-throughput operations with proper indexing and relationships.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from typing import Optional
import bcrypt

Base = declarative_base()

class Client(Base):
    """
    Client model representing award travel customers.
    Optimized with indexes for frequent queries.
    """
    __tablename__ = 'clients'

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False, index=True)
    last_name = Column(String(50), nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20))
    frequent_flyer_number = Column(String(30))
    loyalty_program = Column(String(30))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    # Relationships
    searches = relationship('Search', back_populates='client', cascade='all, delete-orphan')
    intakes = relationship('Intake', back_populates='client', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_client_email', 'email'),
        Index('idx_client_name', 'last_name', 'first_name'),
    )

    def __repr__(self):
        return f"<Client {self.first_name} {self.last_name} ({self.email})>"

class User(Base):
    """
    User model for system authentication.
    Uses bcrypt for secure password hashing.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_login = Column(DateTime)

    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_username', 'username'),
    )

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password: str):
        """Hash password using bcrypt."""
        self.hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.hashed_password.encode('utf-8')
        )

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"

class Search(Base):
    """
    Award search model tracking flight searches.
    Optimized for search performance with proper indexing.
    """
    __tablename__ = 'searches'

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    origin = Column(String(3), nullable=False, index=True)
    destination = Column(String(3), nullable=False, index=True)
    departure_date = Column(DateTime, nullable=False, index=True)
    return_date = Column(DateTime, index=True)
    cabin_class = Column(String(10), nullable=False, index=True)
    adults = Column(Integer, default=1)
    children = Column(Integer, default=0)
    infants = Column(Integer, default=0)
    max_stops = Column(Integer, default=99)
    max_price = Column(Float)
    preferred_airlines = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    client = relationship('Client', back_populates='searches')
    results = relationship('SearchResult', back_populates='search', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_search_route', 'origin', 'destination', 'cabin_class'),
        Index('idx_search_dates', 'departure_date', 'return_date'),
        Index('idx_search_client', 'client_id'),
    )

    def __repr__(self):
        return f"<Search {self.origin}-{self.destination} on {self.departure_date}>"

class SearchResult(Base):
    """
    Individual award search results with caching.
    """
    __tablename__ = 'search_results'

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey('searches.id', ondelete='CASCADE'), nullable=False, index=True)
    airline = Column(String(50), nullable=False)
    flight_number = Column(String(20))
    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    cabin_class = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(3), default='USD')
    duration_minutes = Column(Integer)
    stops = Column(Integer, default=0)
    booking_link = Column(String(500))
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    search = relationship('Search', back_populates='results')

    __table_args__ = (
        Index('idx_result_search', 'search_id'),
        Index('idx_result_route', 'origin', 'destination'),
        Index('idx_result_price', 'price'),
    )

    def __repr__(self):
        return f"<SearchResult {self.airline} {self.flight_number} {self.price}>"

class Intake(Base):
    """
    Form intake data from clients.
    """
    __tablename__ = 'intakes'

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    travel_date = Column(DateTime)
    destination = Column(String(100))
    budget = Column(Float)
    notes = Column(String(500))
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    client = relationship('Client', back_populates='intakes')

    __table_args__ = (
        Index('idx_intake_client', 'client_id'),
        Index('idx_intake_status', 'status'),
    )

    def __repr__(self):
        return f"<Intake {self.first_name} {self.last_name} - {self.status}>"
