"""
Payment History Pipeline Module
Handles processing and storing payment history data with audit trails
"""

import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/payment_history.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PaymentHistoryError(Exception):
    """Base exception for payment history operations"""
    pass

class PaymentHistoryStore:
    """SQLite-backed payment history storage with audit trails"""

    def __init__(self, db_path: str = 'data/payment_history.db'):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database schema with proper indexes for performance"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS payment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    booking_reference TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    payment_method TEXT NOT NULL,
                    transaction_id TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    audit_trail TEXT
                )
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS payment_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    performed_by TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (payment_id) REFERENCES payment_history(id)
                )
                """)

                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_user ON payment_history(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_booking ON payment_history(booking_reference)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_transaction ON payment_history(transaction_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_status ON payment_history(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_created ON payment_history(created_at)")

                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            raise PaymentHistoryError(f"Database initialization failed: {e}")

    def record_payment(self, payment_data: Dict) -> Tuple[int, str]:
        """
        Record a new payment with audit trail

        Args:
            payment_data: Dictionary containing payment details

        Returns:
            Tuple of (payment_id, transaction_id)
        """
        required_fields = ['user_id', 'booking_reference', 'amount', 'payment_method', 'transaction_id', 'status']
        for field in required_fields:
            if field not in payment_data:
                raise PaymentHistoryError(f"Missing required field: {field}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert payment record
                cursor.execute("""
                INSERT INTO payment_history
                (user_id, booking_reference, amount, currency, payment_method, transaction_id, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    payment_data['user_id'],
                    payment_data['booking_reference'],
                    payment_data['amount'],
                    payment_data.get('currency', 'USD'),
                    payment_data['payment_method'],
                    payment_data['transaction_id'],
                    payment_data['status'],
                    json.dumps(payment_data.get('metadata', {}))
                ))

                payment_id = cursor.lastrowid
                transaction_id = payment_data['transaction_id']

                # Create audit trail
                audit_data = {
                    'action': 'CREATE',
                    'performed_by': 'system',
                    'details': f"Payment recorded for user {payment_data['user_id']}"
                }

                cursor.execute("""
                INSERT INTO payment_audit
                (payment_id, action, performed_by, details)
                VALUES (?, ?, ?, ?)
                """, (
                    payment_id,
                    audit_data['action'],
                    audit_data['performed_by'],
                    json.dumps(audit_data)
                ))

                conn.commit()
                logger.info(f"Recorded payment {transaction_id} for user {payment_data['user_id']}")

                return payment_id, transaction_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Payment record failed (duplicate transaction_id): {e}")
            raise PaymentHistoryError(f"Payment with transaction_id {payment_data['transaction_id']} already exists")
        except sqlite3.Error as e:
            logger.error(f"Payment recording failed: {e}")
            raise PaymentHistoryError(f"Payment recording failed: {e}")

    def update_payment_status(self, transaction_id: str, new_status: str, updated_by: str = 'system') -> bool:
        """
        Update payment status with audit trail

        Args:
            transaction_id: The transaction ID to update
            new_status: New status for the payment
            updated_by: Who performed the update

        Returns:
            True if update was successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get current payment
                cursor.execute("""
                SELECT id, status FROM payment_history WHERE transaction_id = ?
                """, (transaction_id,))
                result = cursor.fetchone()

                if not result:
                    logger.warning(f"Update failed: transaction {transaction_id} not found")
                    return False

                payment_id, old_status = result

                if old_status == new_status:
                    logger.info(f"Status update skipped: transaction {transaction_id} already has status {new_status}")
                    return True

                # Update payment record
                cursor.execute("""
                UPDATE payment_history
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE transaction_id = ?
                """, (new_status, transaction_id))

                # Create audit trail
                audit_data = {
                    'action': 'UPDATE_STATUS',
                    'performed_by': updated_by,
                    'details': {
                        'old_status': old_status,
                        'new_status': new_status
                    }
                }

                cursor.execute("""
                INSERT INTO payment_audit
                (payment_id, action, performed_by, details)
                VALUES (?, ?, ?, ?)
                """, (
                    payment_id,
                    audit_data['action'],
                    audit_data['performed_by'],
                    json.dumps(audit_data)
                ))

                conn.commit()
                logger.info(f"Updated payment {transaction_id} status from {old_status} to {new_status}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Payment status update failed: {e}")
            raise PaymentHistoryError(f"Payment status update failed: {e}")

    def get_payment_history(self, user_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Retrieve payment history for a user

        Args:
            user_id: User ID to retrieve history for
            limit: Maximum number of records to return
            offset: Offset for pagination

        Returns:
            List of payment history records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                SELECT * FROM payment_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """, (user_id, limit, offset))

                payments = []
                for row in cursor.fetchall():
                    payments.append(dict(row))

                # Get total count for pagination
                cursor.execute("""
                SELECT COUNT(*) as count FROM payment_history WHERE user_id = ?
                """, (user_id,))
                total_count = cursor.fetchone()['count']

                return {
                    'payments': payments,
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + limit < total_count
                }

        except sqlite3.Error as e:
            logger.error(f"Payment history retrieval failed: {e}")
            raise PaymentHistoryError(f"Payment history retrieval failed: {e}")

    def get_payment_details(self, transaction_id: str) -> Optional[Dict]:
        """
        Retrieve details for a specific payment

        Args:
            transaction_id: Transaction ID to retrieve

        Returns:
            Payment details or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                SELECT * FROM payment_history WHERE transaction_id = ?
                """, (transaction_id,))

                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        except sqlite3.Error as e:
            logger.error(f"Payment details retrieval failed: {e}")
            raise PaymentHistoryError(f"Payment details retrieval failed: {e}")

    def search_payments(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search payment history with flexible query

        Args:
            query: Search term (can match booking reference, transaction ID, or user ID)
            limit: Maximum number of results

        Returns:
            List of matching payment records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Try to detect if query is a user ID (numeric)
                try:
                    user_id = int(query)
                    cursor.execute("""
                    SELECT * FROM payment_history
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """, (user_id, limit))
                except ValueError:
                    # Search by transaction ID or booking reference
                    cursor.execute("""
                    SELECT * FROM payment_history
                    WHERE transaction_id LIKE ? OR booking_reference LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """, (f'%{query}%', f'%{query}%', limit))

                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Payment search failed: {e}")
            raise PaymentHistoryError(f"Payment search failed: {e}")

    def get_payment_stats(self, user_id: int) -> Dict:
        """
        Get statistics for a user's payment history

        Args:
            user_id: User ID to get stats for

        Returns:
            Dictionary with payment statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total payments
                cursor.execute("""
                SELECT COUNT(*) as total_payments,
                       SUM(amount) as total_amount,
                       AVG(amount) as avg_amount,
                       MIN(amount) as min_amount,
                       MAX(amount) as max_amount
                FROM payment_history
                WHERE user_id = ?
                """, (user_id,))

                stats = cursor.fetchone()

                # Payment method breakdown
                cursor.execute("""
                SELECT payment_method, COUNT(*) as count,
                       SUM(amount) as total_amount
                FROM payment_history
                WHERE user_id = ?
                GROUP BY payment_method
                """, (user_id,))

                method_stats = cursor.fetchall()

                # Status breakdown
                cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM payment_history
                WHERE user_id = ?
                GROUP BY status
                """, (user_id,))

                status_stats = cursor.fetchall()

                return {
                    'user_id': user_id,
                    'total_payments': stats['total_payments'],
                    'total_amount': stats['total_amount'],
                    'avg_amount': stats['avg_amount'],
                    'min_amount': stats['min_amount'],
                    'max_amount': stats['max_amount'],
                    'payment_methods': [{'method': row['payment_method'], 'count': row['count'], 'total_amount': row['total_amount']} for row in method_stats],
                    'statuses': [{'status': row['status'], 'count': row['count']} for row in status_stats],
                    'last_payment_date': self._get_last_payment_date(conn, user_id)
                }

        except sqlite3.Error as e:
            logger.error(f"Payment stats retrieval failed: {e}")
            raise PaymentHistoryError(f"Payment stats retrieval failed: {e}")

    def _get_last_payment_date(self, conn: sqlite3.Connection, user_id: int) -> Optional[str]:
        """Helper method to get last payment date"""
        cursor = conn.cursor()
        cursor.execute("""
        SELECT MAX(created_at) as last_date FROM payment_history WHERE user_id = ?
        """, (user_id,))
        result = cursor.fetchone()
        return result['last_date'] if result['last_date'] else None

class PaymentHistoryService:
    """Service layer for payment history operations"""

    def __init__(self):
        self.store = PaymentHistoryStore()

    def record_successful_payment(self, payment_data: Dict) -> Tuple[int, str]:
        """Record a successful payment"""
        payment_data['status'] = 'completed'
        return self.store.record_payment(payment_data)

    def record_failed_payment(self, payment_data: Dict) -> Tuple[int, str]:
        """Record a failed payment attempt"""
        payment_data['status'] = 'failed'
        return self.store.record_payment(payment_data)

    def record_refund(self, transaction_id: str, amount: float, refunded_by: str) -> bool:
        """Record a refund transaction"""
        # In a real system, this would integrate with payment processor
        refund_data = {
            'user_id': None,  # Would need to be determined from original payment
            'booking_reference': 'REFUND',
            'amount': amount,
            'payment_method': 'refund',
            'transaction_id': f"REF-{transaction_id}-{int(time.time())}",
            'status': 'completed',
            'metadata': {
                'original_transaction': transaction_id,
                'refunded_by': refunded_by
            }
        }

        _, transaction_id = self.store.record_payment(refund_data)
        self.store.update_payment_status(transaction_id, 'completed', refunded_by)
        return True

    def get_user_payment_history(self, user_id: int, page: int = 1, per_page: int = 20) -> Dict:
        """Get paginated payment history for a user"""
        offset = (page - 1) * per_page
        return self.store.get_payment_history(user_id, limit=per_page, offset=offset)

    def get_payment_details(self, transaction_id: str) -> Optional[Dict]:
        """Get details for a specific payment"""
        return self.store.get_payment_details(transaction_id)

    def search_payments(self, query: str) -> List[Dict]:
        """Search payment history"""
        return self.store.search_payments(query)

    def get_payment_statistics(self, user_id: int) -> Dict:
        """Get statistics for a user's payment history"""
        return self.store.get_payment_stats(user_id)

# Initialize service on import
payment_service = PaymentHistoryService()
