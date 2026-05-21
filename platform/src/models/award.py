from sqlalchemy import Column, Integer, String, Float, Date, Boolean, Index, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import date
from typing import Optional, List
import json

Base = declarative_base()

class Award(Base):
    __tablename__ = "awards"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    program = relationship("Program", back_populates="awards")

    airline = Column(String(10), nullable=False)
    flight_number = Column(String(20))
    departure_airport = Column(String(3), nullable=False)
    arrival_airport = Column(String(3), nullable=False)
    departure_date = Column(Date, nullable=False)
    arrival_date = Column(Date, nullable=False)

    cabin_class = Column(String(20), nullable=False)
    award_type = Column(String(50), nullable=False)  # e.g., "redemption", "upgrade"

    miles_required = Column(Float, nullable=False)
    taxes_fees = Column(Float, default=0.0)
    total_cost = Column(Float, nullable=False)

    availability = Column(Integer, default=1)  # Number of seats available
    is_partner = Column(Boolean, default=False)
    booking_link = Column(String(500))

    # Additional metadata
    fare_basis = Column(String(50))
    booking_class = Column(String(10))
    stopover_allowed = Column(Boolean, default=False)
    open_jaw_allowed = Column(Boolean, default=False)

    # For GPU acceleration - pre-computed features
    gpu_features = Column(JSON)  # Will store vectorized features for GPU processing

    # Indexes for fast searching
    __table_args__ = (
        Index("idx_awards_departure_arrival", "departure_airport", "arrival_airport"),
        Index("idx_awards_departure_date", "departure_date"),
        Index("idx_awards_program", "program_id"),
        Index("idx_awards_cabin_class", "cabin_class"),
        Index("idx_awards_miles", "miles_required"),
        Index("idx_awards_airline", "airline"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "program_id": self.program_id,
            "airline": self.airline,
            "flight_number": self.flight_number,
            "departure_airport": self.departure_airport,
            "arrival_airport": self.arrival_airport,
            "departure_date": self.departure_date.isoformat(),
            "arrival_date": self.arrival_date.isoformat(),
            "cabin_class": self.cabin_class,
            "award_type": self.award_type,
            "miles_required": self.miles_required,
            "taxes_fees": self.taxes_fees,
            "total_cost": self.total_cost,
            "availability": self.availability,
            "is_partner": self.is_partner,
            "booking_link": self.booking_link,
            "fare_basis": self.fare_basis,
            "booking_class": self.booking_class,
            "stopover_allowed": self.stopover_allowed,
            "open_jaw_allowed": self.open_jaw_allowed,
        }

    def to_gpu_features(self) -> dict:
        """Convert award data to a feature vector for GPU processing"""
        return {
            "miles": self.miles_required,
            "taxes": self.taxes_fees,
            "duration": (self.arrival_date - self.departure_date).days,
            "is_partner": int(self.is_partner),
            "cabin_class_num": self._cabin_to_num(),
            "airline_hash": hash(self.airline) % 1000,
            "dep_airport_hash": hash(self.departure_airport) % 1000,
            "arr_airport_hash": hash(self.arrival_airport) % 1000,
        }

    def _cabin_to_num(self) -> int:
        cabin_map = {
            "economy": 0,
            "premium_economy": 1,
            "business": 2,
            "first": 3
        }
        return cabin_map.get(self.cabin_class.lower(), 0)

class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    airline = Column(String(10), nullable=False)
    currency = Column(String(3), nullable=False)  # e.g., "Miles", "Points"

    awards = relationship("Award", back_populates="program")

    __table_args__ = (
        Index("idx_programs_airline", "airline"),
        Index("idx_programs_name", "name"),
    )
