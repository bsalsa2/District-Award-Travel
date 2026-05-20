import asyncpg
from typing import Optional, List, Dict, Any
from config import config
import logging
from datetime import datetime, timedelta
from common.logger import logger

class DatabaseConnectionPool:
    def __init__(self):
        self.pool = None
        self.config = config.database

    async def initialize(self):
        """Initialize the connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.db_name,
                user=self.config.user,
                password=self.config.password,
                min_size=5,
                max_size=20,
                ssl=self.config.ssl_mode if self.config.ssl_mode != "disable" else None
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise

    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def execute(self, query: str, *args):
        """Execute a query without returning results."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch rows from a query."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Fetch a single row from a query."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value from a query."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def get_prediction_history(
        self,
        route_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical predictions for a route."""
        query = """
        SELECT
            prediction_id, route_id, departure_date, arrival_date,
            predicted_availability, confidence_score, model_version,
            created_at, airline, cabin_class
        FROM flight_predictions
        WHERE route_id = $1
          AND departure_date BETWEEN $2 AND $3
        ORDER BY created_at DESC
        LIMIT $4
        """
        rows = await self.fetch(
            query,
            route_id,
            start_date,
            end_date,
            limit
        )
        return [dict(row) for row in rows]

    async def store_prediction(
        self,
        route_id: str,
        departure_date: datetime,
        arrival_date: datetime,
        predicted_availability: int,
        confidence_score: float,
        model_version: str,
        airline: str,
        cabin_class: str,
        features: Dict[str, Any]
    ) -> str:
        """Store a prediction in the database."""
        query = """
        INSERT INTO flight_predictions (
            route_id, departure_date, arrival_date, predicted_availability,
            confidence_score, model_version, airline, cabin_class, features
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING prediction_id
        """
        prediction_id = await self.fetchval(
            query,
            route_id,
            departure_date,
            arrival_date,
            predicted_availability,
            confidence_score,
            model_version,
            airline,
            cabin_class,
            features
        )
        return prediction_id

    async def get_active_models(self) -> List[Dict[str, Any]]:
        """Get all active model versions."""
        query = """
        SELECT model_version, model_type, accuracy, last_trained_at, status
        FROM models
        WHERE status = 'active'
        ORDER BY last_trained_at DESC
        """
        rows = await self.fetch(query)
        return [dict(row) for row in rows]

    async def update_model_accuracy(
        self,
        model_version: str,
        accuracy: float,
        loss: float,
        test_set: str = 'validation'
    ) -> None:
        """Update model accuracy metrics."""
        query = """
        UPDATE models
        SET accuracy = $1, loss = $2, last_trained_at = NOW()
        WHERE model_version = $3
        """
        await self.execute(query, accuracy, loss, model_version)

        # Log the update
        logger.info(f"Updated model {model_version} accuracy to {accuracy:.4f}")

    async def log_ab_test_result(
        self,
        test_name: str,
        variant: str,
        impressions: int,
        conversions: int,
        conversion_rate: float
    ) -> None:
        """Log A/B test results."""
        query = """
        INSERT INTO ab_test_results (
            test_name, variant, impressions, conversions, conversion_rate, created_at
        ) VALUES ($1, $2, $3, $4, $5, NOW())
        """
        await self.execute(query, test_name, variant, impressions, conversions, conversion_rate)

    async def get_ab_test_variants(self, test_name: str) -> List[Dict[str, Any]]:
        """Get all variants for an A/B test."""
        query = """
        SELECT variant, weight, description
        FROM ab_test_variants
        WHERE test_name = $1
        ORDER BY created_at
        """
        rows = await self.fetch(query, test_name)
        return [dict(row) for row in rows]

# Global database instance
db = DatabaseConnectionPool()
