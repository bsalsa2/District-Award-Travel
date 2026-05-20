"""
Database connection and session management.
Optimized for high-throughput operations with connection pooling.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
import os
from typing import Generator

# Database URL - use environment variable or default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./district_award.db")

# Optimized connection pool configuration
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False  # Set to True for debugging in development
)

# Scoped session factory for thread-safe operations
SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False
    )
)

Base = declarative_base()

def get_db() -> Generator:
    """
    Dependency to get DB session.
    Properly handles session lifecycle with context management.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database tables.
    """
    Base.metadata.create_all(bind=engine)
