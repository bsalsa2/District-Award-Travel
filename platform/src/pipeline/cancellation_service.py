import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum
import uuid
import time
from dataclasses import dataclass
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cancellation_service')

class CancellationStatus(Enum):
    """Status of a cancellation request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class RefundMethod(Enum):
    """Refund methods available."""
    ORIGINAL_PAYMENT = "original_payment"
    TRAVEL_CREDIT = "travel_credit"
    MIXED = "mixed"

@dataclass
class CancellationRequest:
    """Data class representing a cancellation request."""
    request_id: str
    booking_id: str
    user_id: str
    reason: str
    requested_at: datetime
    status: CancellationStatus
    refund_amount: float
    refund_method: RefundMethod
    processed_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CancellationService:
    """
    Service for handling booking cancellations and refunds.
    Designed for high availability and financial accuracy.
    """

    def __init__(self, db_path: str = "platform/data/bookings.db"):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the cancellation database schema."""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Create cancellations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cancellations (
                    request_id TEXT PRIMARY KEY,
                    booking_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    reason TEXT,
                    requested_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    refund_amount REAL NOT NULL,
                    refund_method TEXT NOT NULL,
                    processed_at TEXT,
                    notes TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create cancellation events table for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cancellation_events (
                    event_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES cancellations(request_id)
                )
            """)

            # Create refunds table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    booking_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    method TEXT NOT NULL,
                    status TEXT NOT NULL,
                    transaction_reference TEXT,
                    processed_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES cancellations(request_id)
                )
            """)

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cancellations_booking ON cancellations(booking_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cancellations_user ON cancellations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cancellations_status ON cancellations(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_booking ON refunds(booking_id)")

            conn.commit()

    @contextmanager
    def _get_db_connection(self):
        """Context manager for database connections with retry logic."""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
                conn.row_factory = sqlite3.Row
                yield conn
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                        raise
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"Database connection error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected database error: {e}")
                raise
            finally:
                try:
                    conn.close()
                except:
                    pass

    def create_cancellation_request(
        self,
        booking_id: str,
        user_id: str,
        reason: str,
        refund_amount: float,
        refund_method: RefundMethod = RefundMethod.ORIGINAL_PAYMENT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CancellationRequest:
        """
        Create a new cancellation request.

        Args:
            booking_id: ID of the booking to cancel
            user_id: ID of the user requesting cancellation
            reason: Reason for cancellation
            refund_amount: Amount to refund
            refund_method: Method of refund
            metadata: Additional metadata

        Returns:
            Created CancellationRequest object
        """
        request_id = str(uuid.uuid4())
        requested_at = datetime.utcnow()

        cancellation = CancellationRequest(
            request_id=request_id,
            booking_id=booking_id,
            user_id=user_id,
            reason=reason,
            requested_at=requested_at,
            status=CancellationStatus.PENDING,
            refund_amount=refund_amount,
            refund_method=refund_method,
            metadata=metadata or {}
        )

        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Insert cancellation record
            cursor.execute("""
                INSERT INTO cancellations (
                    request_id, booking_id, user_id, reason, requested_at, status,
                    refund_amount, refund_method, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cancellation.request_id,
                cancellation.booking_id,
                cancellation.user_id,
                cancellation.reason,
                cancellation.requested_at.isoformat(),
                cancellation.status.value,
                cancellation.refund_amount,
                cancellation.refund_method.value,
                requested_at.isoformat(),
                requested_at.isoformat()
            ))

            # Log creation event
            self._log_cancellation_event(
                conn,
                request_id,
                "request_created",
                {
                    "booking_id": booking_id,
                    "user_id": user_id,
                    "amount": refund_amount,
                    "method": refund_method.value
                }
            )

            conn.commit()

        logger.info(f"Created cancellation request {request_id} for booking {booking_id}")
        return cancellation

    def _log_cancellation_event(
        self,
        conn: sqlite3.Connection,
        request_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """Log a cancellation event to the audit trail."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cancellation_events (
                event_id, request_id, event_type, event_data, timestamp
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            event_id,
            request_id,
            event_type,
            json.dumps(event_data),
            timestamp
        ))

    def process_cancellation(
        self,
        request_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Process a cancellation request.

        Args:
            request_id: ID of the cancellation request
            user_id: ID of the user processing the cancellation
            notes: Additional notes about the processing

        Returns:
            True if processing was successful, False otherwise
        """
        with self._get_db_connection() as conn:
            # Get cancellation request
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cancellations WHERE request_id = ?
            """, (request_id,))
            row = cursor.fetchone()

            if not row:
                logger.warning(f"Cancellation request {request_id} not found")
                return False

            cancellation = CancellationRequest(
                request_id=row['request_id'],
                booking_id=row['booking_id'],
                user_id=row['user_id'],
                reason=row['reason'],
                requested_at=datetime.fromisoformat(row['requested_at']),
                status=CancellationStatus(row['status']),
                refund_amount=row['refund_amount'],
                refund_method=RefundMethod(row['refund_method']),
                processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
                notes=row['notes'],
                metadata=json.loads(row['metadata']) if row['metadata'] else None
            )

            # Check if already processed
            if cancellation.status != CancellationStatus.PENDING:
                logger.warning(f"Cancellation request {request_id} is already {cancellation.status.value}")
                return False

            # Update status to processing
            processing_time = datetime.utcnow()
            cursor.execute("""
                UPDATE cancellations
                SET status = ?, processed_at = ?, updated_at = ?
                WHERE request_id = ?
            """, (
                CancellationStatus.PROCESSING.value,
                processing_time.isoformat(),
                processing_time.isoformat(),
                request_id
            ))

            # Log processing event
            self._log_cancellation_event(
                conn,
                request_id,
                "processing_started",
                {
                    "processed_by": user_id,
                    "timestamp": processing_time.isoformat()
                }
            )

            conn.commit()

            # Simulate refund processing (in a real system, this would integrate with payment processors)
            try:
                refund_id = str(uuid.uuid4())
                refund_processed_at = datetime.utcnow()

                # Insert refund record
                cursor.execute("""
                    INSERT INTO refunds (
                        refund_id, request_id, booking_id, user_id, amount, method, status, processed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    refund_id,
                    request_id,
                    cancellation.booking_id,
                    cancellation.user_id,
                    cancellation.refund_amount,
                    cancellation.refund_method.value,
                    "completed",
                    refund_processed_at.isoformat(),
                    refund_processed_at.isoformat()
                ))

                # Update cancellation status to completed
                cursor.execute("""
                    UPDATE cancellations
                    SET status = ?, notes = ?, updated_at = ?
                    WHERE request_id = ?
                """, (
                    CancellationStatus.COMPLETED.value,
                    notes or "Cancellation processed successfully",
                    datetime.utcnow().isoformat(),
                    request_id
                ))

                # Log completion event
                self._log_cancellation_event(
                    conn,
                    request_id,
                    "processing_completed",
                    {
                        "refund_id": refund_id,
                        "amount": cancellation.refund_amount,
                        "method": cancellation.refund_method.value,
                        "processed_at": refund_processed_at.isoformat()
                    }
                )

                conn.commit()
                logger.info(f"Successfully processed cancellation {request_id}")
                return True

            except Exception as e:
                # Update status to failed
                cursor.execute("""
                    UPDATE cancellations
                    SET status = ?, notes = ?, updated_at = ?
                    WHERE request_id = ?
                """, (
                    CancellationStatus.FAILED.value,
                    f"Processing failed: {str(e)}",
                    datetime.utcnow().isoformat(),
                    request_id
                ))

                # Log failure event
                self._log_cancellation_event(
                    conn,
                    request_id,
                    "processing_failed",
                    {
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

                conn.commit()
                logger.error(f"Failed to process cancellation {request_id}: {e}")
                return False

    def get_cancellation_status(self, request_id: str) -> Optional[CancellationRequest]:
        """
        Get the status of a cancellation request.

        Args:
            request_id: ID of the cancellation request

        Returns:
            CancellationRequest object if found, None otherwise
        """
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cancellations WHERE request_id = ?
            """, (request_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return CancellationRequest(
                request_id=row['request_id'],
                booking_id=row['booking_id'],
                user_id=row['user_id'],
                reason=row['reason'],
                requested_at=datetime.fromisoformat(row['requested_at']),
                status=CancellationStatus(row['status']),
                refund_amount=row['refund_amount'],
                refund_method=RefundMethod(row['refund_method']),
                processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
                notes=row['notes'],
                metadata=json.loads(row['metadata']) if row['metadata'] else None
            )

    def get_cancellation_history(self, user_id: str, limit: int = 50) -> list[CancellationRequest]:
        """
        Get cancellation history for a user.

        Args:
            user_id: ID of the user
            limit: Maximum number of records to return

        Returns:
            List of CancellationRequest objects
        """
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cancellations
                WHERE user_id = ?
                ORDER BY requested_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

            return [
                CancellationRequest(
                    request_id=row['request_id'],
                    booking_id=row['booking_id'],
                    user_id=row['user_id'],
                    reason=row['reason'],
                    requested_at=datetime.fromisoformat(row['requested_at']),
                    status=CancellationStatus(row['status']),
                    refund_amount=row['refund_amount'],
                    refund_method=RefundMethod(row['refund_method']),
                    processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
                    notes=row['notes'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else None
                )
                for row in rows
            ]

    def validate_cancellation_eligibility(
        self,
        booking_id: str,
        cancellation_time: datetime
    ) -> tuple[bool, str]:
        """
        Validate if a booking can be cancelled based on business rules.

        Args:
            booking_id: ID of the booking
            cancellation_time: Time of cancellation request

        Returns:
            Tuple of (is_eligible, reason) where is_eligible is a boolean
            and reason is a string explaining the decision
        """
        # In a real system, this would check business rules like:
        # - Time since booking
        # - Time until travel
        # - Booking type
        # - User status
        # - Special promotions

        # For now, implement a simple rule: can cancel up to 24 hours before travel
        # This would be replaced with actual business logic in production

        # Simulate getting booking details
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Get booking details (simplified)
            cursor.execute("""
                SELECT travel_date FROM bookings WHERE booking_id = ?
            """, (booking_id,))
            row = cursor.fetchone()

            if not row:
                return False, "Booking not found"

            travel_date = datetime.fromisoformat(row['travel_date'])
            time_until_travel = (travel_date - cancellation_time).total_seconds() / 3600  # hours

            if time_until_travel < 24:
                return False, "Cannot cancel within 24 hours of travel"

            return True, "Eligible for cancellation"

# API Interface for the cancellation service
class CancellationAPI:
    """API interface for the cancellation service."""

    def __init__(self, service: CancellationService):
        self.service = service

    def create_cancellation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cancellation request creation."""
        try:
            booking_id = data['booking_id']
            user_id = data['user_id']
            reason = data.get('reason', 'Customer requested cancellation')
            refund_amount = float(data['refund_amount'])
            refund_method = RefundMethod(data.get('refund_method', RefundMethod.ORIGINAL_PAYMENT.value))

            cancellation = self.service.create_cancellation_request(
                booking_id=booking_id,
                user_id=user_id,
                reason=reason,
                refund_amount=refund_amount,
                refund_method=refund_method,
                metadata=data.get('metadata')
            )

            return {
                "success": True,
                "request_id": cancellation.request_id,
                "status": cancellation.status.value,
                "message": "Cancellation request created successfully"
            }
        except Exception as e:
            logger.error(f"Failed to create cancellation: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def process_cancellation(self, request_id: str, user_id: str) -> Dict[str, Any]:
        """Handle cancellation processing."""
        try:
            success = self.service.process_cancellation(
                request_id=request_id,
                user_id=user_id,
                notes="Processed via API"
            )

            if success:
                return {
                    "success": True,
                    "message": "Cancellation processed successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to process cancellation"
                }
        except Exception as e:
            logger.error(f"Failed to process cancellation {request_id}: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def get_status(self, request_id: str) -> Dict[str, Any]:
        """Get cancellation status."""
        try:
            cancellation = self.service.get_cancellation_status(request_id)
            if cancellation:
                return {
                    "success": True,
                    "status": cancellation.status.value,
                    "request_id": cancellation.request_id,
                    "booking_id": cancellation.booking_id,
                    "refund_amount": cancellation.refund_amount,
                    "refund_method": cancellation.refund_method.value,
                    "requested_at": cancellation.requested_at.isoformat(),
                    "processed_at": cancellation.processed_at.isoformat() if cancellation.processed_at else None,
                    "notes": cancellation.notes
                }
            else:
                return {
                    "success": False,
                    "message": "Cancellation request not found"
                }
        except Exception as e:
            logger.error(f"Failed to get cancellation status: {e}")
            return {
                "success": False,
                "message": str(e)
            }

# Example usage
if __name__ == "__main__":
    # Initialize service
    service = CancellationService()
    api = CancellationAPI(service)

    # Example: Create a cancellation request
    response = api.create_cancellation({
        "booking_id": "BOOK-12345",
        "user_id": "USER-67890",
        "reason": "Change of plans",
        "refund_amount": 1250.00,
        "refund_method": RefundMethod.ORIGINAL_PAYMENT.value
    })

    print("Create cancellation response:", response)

    if response["success"]:
        request_id = response["request_id"]

        # Example: Process the cancellation
        process_response = api.process_cancellation(
            request_id=request_id,
            user_id="AGENT-123"
        )

        print("Process cancellation response:", process_response)

        # Example: Get status
        status_response = api.get_status(request_id)
        print("Status response:", status_response)
