"""
Database models for District Award Travel AI Assistant
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Dict, Any

Base = declarative_base()

class Client(Base):
    """Client model for storing user information"""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(64), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(32))
    loyalty_program = Column(String(64))
    loyalty_number = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    preferences = Column(JSON, default={})
    travel_history = Column(JSON, default=[])

class Conversation(Base):
    """Conversation model for storing chat interactions"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), unique=True, index=True, nullable=False)
    client_id = Column(String(64), index=True, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String(32), default="active")  # active, completed, failed
    metadata = Column(JSON, default={})
    messages = Column(JSON, default=[])

class AwardSearch(Base):
    """Award search model for storing search queries and results"""
    __tablename__ = "award_searches"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(String(64), unique=True, index=True, nullable=False)
    client_id = Column(String(64), index=True)
    query = Column(Text, nullable=False)
    query_vector = Column(JSON)  # For vector similarity search
    results = Column(JSON, default=[])
    filters = Column(JSON, default={})
    sort_by = Column(String(32), default="value")
    limit = Column(Integer, default=10)
    offset = Column(Integer, default=0)
    total_results = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(32), default="pending")  # pending, processing, completed, failed

class AwardRecommendation(Base):
    """Award recommendation model"""
    __tablename__ = "award_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(String(64), unique=True, index=True, nullable=False)
    client_id = Column(String(64), index=True)
    search_id = Column(String(64), index=True)
    award_id = Column(String(64), nullable=False)
    program = Column(String(64), nullable=False)
    value = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    description = Column(Text)
    conditions = Column(JSON, default={})
    availability = Column(JSON, default={})
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default={})

class Feedback(Base):
    """Feedback model for user feedback on recommendations"""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(String(64), unique=True, index=True, nullable=False)
    client_id = Column(String(64), index=True)
    conversation_id = Column(String(64), index=True)
    recommendation_id = Column(String(64), index=True)
    rating = Column(Integer)  # 1-5
    comment = Column(Text)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemLog(Base):
    """System log model for observability"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(64), unique=True, index=True, nullable=False)
    level = Column(String(16), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    service = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    context = Column(JSON, default={})
    timestamp = Column(DateTime, default=datetime.utcnow)
    trace_id = Column(String(64))
    span_id = Column(String(64))
