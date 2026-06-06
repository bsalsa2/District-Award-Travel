"""
Booking Pipeline - Distributed processing pipeline for travel bookings
Handles async processing, validation, and state management
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from platform.src.db.database import (
    get_booking, get_bookings, create_booking,
    update_booking, delete_booking, get_user_bookings
)
from platform.src.intelligence.valuation_engine import ValuationEngine
from platform.src.db.database import db
import asyncio

logger = logging.getLogger(__name__)

class BookingPipeline:
    """Main booking processing pipeline"""

    def __init__(self):
        self.valuation_engine = ValuationEngine()
        self.processing_queue = asyncio.Queue(maxsize=1000)
        self.workers = []

    async def initialize(self):
        """Initialize pipeline workers"""
        for i in range(4):  # 4 worker threads
            worker = asyncio.create_task(self._worker_loop(i))
            self.workers.append(worker)
        logger.info("Booking pipeline initialized with %d workers", len(self.workers))

    async def _worker_loop(self, worker_id: int):
        """Worker loop for processing bookings"""
        logger.info("Worker %d started", worker_id)
        while True:
            try:
                task = await self.processing_queue.get()
                await self._process_task(task)
                self.processing_queue.task_done()
            except Exception as e:
                logger.error("Worker %d error: %s", worker_id, str(e))

    async def _process_task(self, task: Dict[str, Any]):
        """Process a booking task"""
        try:
            if task['type'] == 'create':
                await self._process_create_booking(task['data'])
            elif task['type'] == 'update':
                await self._process_update_booking(task['booking_id'], task['data'])
            elif task['type'] == 'delete':
                await self._process_delete_booking(task['booking_id'])
            logger.info("Processed task: %s", task['type'])
        except Exception as e:
            logger.error("Failed to process task: %s", str(e))

    async def _process_create_booking(self, booking_data: Dict[str, Any]):
        """Process booking creation with validation and valuation"""
        try:
            # Validate required fields
            required_fields = ['user_id', 'flight_number', 'departure_date', 'cabin_class', 'award_points']
            for field in required_fields:
                if field not in booking_data:
                    raise ValueError(f"Missing required field: {field}")

            # Calculate valuation
            valuation = self.valuation_engine.calculate_valuation(
                booking_data['flight_number'],
                booking_data['cabin_class'],
                booking_data['departure_date'],
                booking_data.get('return_date')
            )

            # Update booking data with valuation
            booking_data['award_points'] = valuation['award_points']

            # Create booking in database
            async with db.get_connection() as conn:
                booking = await create_booking(conn, booking_data)

            logger.info("Created booking: %s", booking['id'])
            return booking
        except Exception as e:
            logger.error("Failed to create booking: %s", str(e))
            raise

    async def _process_update_booking(self, booking_id: int, booking_data: Dict[str, Any]):
        """Process booking update"""
        try:
            async with db.get_connection() as conn:
                booking = await update_booking(conn, booking_id, booking_data)
            logger.info("Updated booking: %s", booking_id)
            return booking
        except Exception as e:
            logger.error("Failed to update booking %s: %s", booking_id, str(e))
            raise

    async def _process_delete_booking(self, booking_id: int):
        """Process booking deletion"""
        try:
            async with db.get_connection() as conn:
                success = await delete_booking(conn, booking_id)
            logger.info("Deleted booking: %s", booking_id)
            return success
        except Exception as e:
            logger.error("Failed to delete booking %s: %s", booking_id, str(e))
            raise

    # Public API methods
    async def get_booking(self, booking_id: int) -> Optional[Dict[str, Any]]:
        """Get a single booking"""
        try:
            async with db.get_connection() as conn:
                booking = await get_booking(conn, booking_id)
            return booking
        except Exception as e:
            logger.error("Failed to get booking %s: %s", booking_id, str(e))
            raise

    async def get_bookings(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get list of bookings with pagination"""
        try:
            async with db.get_connection() as conn:
                bookings = await get_bookings(conn, limit=limit, offset=offset)
            return bookings
        except Exception as e:
            logger.error("Failed to get bookings: %s", str(e))
            raise

    async def get_recent_bookings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent bookings for dashboard"""
        try:
            async with db.get_connection() as conn:
                bookings = await get_bookings(conn, limit=limit, offset=0)
            return bookings
        except Exception as e:
            logger.error("Failed to get recent bookings: %s", str(e))
            raise

    async def create_booking(self, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new booking via pipeline"""
        try:
            task = {
                'type': 'create',
                'data': booking_data
            }
            await self.processing_queue.put(task)
            # For synchronous response, we'll wait for the task to complete
            # In production, you might use a callback or event system
            return await self.get_booking_by_flight(
                booking_data['flight_number'],
                booking_data['departure_date']
            )
        except Exception as e:
            logger.error("Failed to create booking: %s", str(e))
            raise

    async def update_booking(self, booking_id: int, booking_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing booking via pipeline"""
        try:
            task = {
                'type': 'update',
                'booking_id': booking_id,
                'data': booking_data
            }
            await self.processing_queue.put(task)
            return await self.get_booking(booking_id)
        except Exception as e:
            logger.error("Failed to update booking %s: %s", booking_id, str(e))
            raise

    async def delete_booking(self, booking_id: int) -> bool:
        """Delete a booking via pipeline"""
        try:
            task = {
                'type': 'delete',
                'booking_id': booking_id
            }
            await self.processing_queue.put(task)
            return True
        except Exception as e:
            logger.error("Failed to delete booking %s: %s", booking_id, str(e))
            raise

    async def get_user_bookings(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all bookings for a user"""
        try:
            async with db.get_connection() as conn:
                bookings = await get_user_bookings(conn, user_id, limit=limit)
            return bookings
        except Exception as e:
            logger.error("Failed to get user bookings for %s: %s", user_id, str(e))
            raise

    async def get_booking_by_flight(self, flight_number: str, departure_date: str) -> Optional[Dict[str, Any]]:
        """Get booking by flight number and date"""
        try:
            async with db.get_connection() as conn:
                result = await conn.execute(
                    "SELECT * FROM bookings WHERE flight_number = ? AND departure_date = ?",
                    (flight_number, departure_date)
                )
                row = await result.fetchone()
                if not row:
                    return None
                columns = [column[0] for column in result.description]
                return dict(zip(columns, row))
        except Exception as e:
            logger.error("Failed to get booking by flight: %s", str(e))
            raise

# Initialize pipeline
pipeline = BookingPipeline()
asyncio.run(pipeline.initialize())
