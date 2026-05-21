from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from typing import AsyncGenerator, Optional
import logging
from ..config import config
from ..models.award import Base

logger = logging.getLogger(__name__)

class Database:
    """
    PostgreSQL database connection manager with async support.
    Optimized for high-throughput award travel queries.
    """

    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.async_session: Optional[sessionmaker] = None
        self.Base = declarative_base()

    async def connect(self):
        """Create database engine and session factory"""
        try:
            # Create async engine with optimized settings
            self.engine = create_async_engine(
                f"postgresql+asyncpg://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}@"
                f"{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}",
                pool_size=config.POSTGRES_POOL_SIZE,
                max_overflow=config.POSTGRES_MAX_OVERFLOW,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
                connect_args={
                    "command_timeout": config.QUERY_TIMEOUT,
                    "server_settings": {
                        "jit": "off",  # Disable JIT for more predictable performance
                        "enable_seqscan": "off",  # Prefer index scans
                        "random_page_cost": "1.1",  # SSD storage
                        "effective_cache_size": "10GB",  # Adjust based on your system
                    }
                }
            )

            # Create session factory
            self.async_session = sessionmaker(
                self.engine,
                expire_on_commit=False,
                class_=AsyncSession
            )

            logger.info("PostgreSQL database connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("PostgreSQL database connections closed")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        if not self.async_session:
            await self.connect()

        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

    async def initialize_schema(self):
        """Initialize database schema"""
        if not self.engine:
            await self.connect()

        async with self.engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)

            # Create indexes if they don't exist
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_awards_departure_arrival
                ON awards (departure_airport, arrival_airport)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_awards_departure_date
                ON awards (departure_date)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_awards_program
                ON awards (program_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_awards_cabin_class
                ON awards (cabin_class)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_awards_miles
                ON awards (miles_required)
            """)

            logger.info("PostgreSQL schema initialized")

# Singleton instance
db = Database()
