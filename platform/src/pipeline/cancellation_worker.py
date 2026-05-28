"""
Cancellation Processing Worker
Handles asynchronous cancellation requests and refund processing
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from decimal import Decimal
import json
from pathlib import Path

from platform.src.policy.cancellation import (
    cancellation_engine,
    CancellationStatus,
    BookingClass,
    FareType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CancellationWorker:
    """Worker for processing cancellation requests"""

    def __init__(self, work_queue: asyncio.Queue, result_queue: asyncio.Queue):
        self.work_queue = work_queue
        self.result_queue = result_queue
        self.running = False

    async def process_cancellation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single cancellation request"""
        try:
            # Extract request data
            booking_id = request.get('booking_id')
            booking_class = BookingClass(request.get('booking_class', 'economy'))
            fare_type = FareType(request.get('fare_type', 'discounted'))
            original_amount = Decimal(request.get('original_amount', '0'))
            departure_date_str = request.get('departure_date')
            cancellation_date_str = request.get('cancellation_date', datetime.utcnow().isoformat())

            # Parse dates
            departure_date = datetime.fromisoformat(departure_date_str)
            cancellation_date = datetime.fromisoformat(cancellation_date_str)

            # Calculate cancellation details
            result = cancellation_engine.calculate_cancellation(
                booking_class=booking_class,
                fare_type=fare_type,
                original_amount=original_amount,
                departure_date=departure_date,
                cancellation_date=cancellation_date
            )

            # Simulate processing delay
            await asyncio.sleep(0.5)

            # Update result with booking info
            result.update({
                "booking_id": booking_id,
                "status": CancellationStatus.PROCESSED.value,
                "processed_at": datetime.utcnow().isoformat(),
                "success": True
            })

            return result

        except Exception as e:
            logger.error(f"Error processing cancellation for booking {booking_id}: {str(e)}")
            return {
                "booking_id": booking_id,
                "status": CancellationStatus.FAILED.value,
                "error": str(e),
                "success": False,
                "processed_at": datetime.utcnow().isoformat()
            }

    async def worker_loop(self):
        """Main worker loop"""
        self.running = True
        logger.info("Cancellation worker started")

        while self.running:
            try:
                # Get next request
                request = await self.work_queue.get()

                if request is None:  # Sentinel value to stop
                    break

                # Process cancellation
                result = await self.process_cancellation(request)

                # Put result in output queue
                await self.result_queue.put(result)

                # Mark task as done
                self.work_queue.task_done()

            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
                self.work_queue.task_done()

        logger.info("Cancellation worker stopped")

    async def stop(self):
        """Stop the worker"""
        self.running = False

class CancellationManager:
    """Manager for handling cancellation workflows"""

    def __init__(self):
        self.work_queue = asyncio.Queue()
        self.result_queue = asyncio.Queue()
        self.workers = []
        self.worker_count = 4  # Number of concurrent workers

    async def start(self):
        """Start the cancellation processing system"""
        # Create and start workers
        for i in range(self.worker_count):
            worker = CancellationWorker(self.work_queue, self.result_queue)
            task = asyncio.create_task(worker.worker_loop())
            self.workers.append((worker, task))

        logger.info(f"Started {self.worker_count} cancellation workers")

    async def stop(self):
        """Stop all workers"""
        # Send sentinel values to stop workers
        for _ in range(self.worker_count):
            await self.work_queue.put(None)

        # Wait for workers to finish
        await asyncio.gather(*[worker[1] for worker in self.workers])

        logger.info("All cancellation workers stopped")

    async def submit_cancellation(self, request: Dict[str, Any]) -> str:
        """Submit a new cancellation request"""
        request_id = f"cancel-{datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')}"
        request['request_id'] = request_id

        await self.work_queue.put(request)
        logger.info(f"Submitted cancellation request: {request_id}")

        return request_id

    async def get_result(self) -> Dict[str, Any]:
        """Get next available result"""
        return await self.result_queue.get()

    async def process_cancellation_sync(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for cancellation processing"""
        # For testing or simple cases
        return await self.process_cancellation(request)

# Global manager instance
cancellation_manager = CancellationManager()

async def main():
    """Test the cancellation system"""
    await cancellation_manager.start()

    # Test request
    test_request = {
        "booking_id": "AWARD-2026-001",
        "booking_class": "business",
        "fare_type": "full_fare",
        "original_amount": "1250.00",
        "departure_date": "2026-06-15T00:00:00"
    }

    request_id = await cancellation_manager.submit_cancellation(test_request)
    print(f"Submitted cancellation request: {request_id}")

    result = await cancellation_manager.get_result()
    print("Cancellation result:")
    print(json.dumps(result, indent=2))

    await cancellation_manager.stop()

if __name__ == "__main__":
    asyncio.run(main())
