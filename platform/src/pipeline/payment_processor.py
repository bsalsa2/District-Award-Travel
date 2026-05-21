"""
Payment Processing Pipeline
Handles asynchronous payment processing with:
- Queue-based processing
- Dead letter queue for failed payments
- Monitoring and alerting
- Audit logging
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass
import sqlite3
import threading
from queue import Queue, Empty
from platform.src.payment.gateway import PaymentRequest, PaymentResponse, PaymentStatus, gateway

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PaymentProcessor')

@dataclass
class PaymentJob:
    """Data class for payment processing jobs"""
    job_id: str
    payment_request: PaymentRequest
    created_at: str = datetime.utcnow().isoformat()
    retries: int = 0
    last_attempt: Optional[str] = None

class PaymentProcessor:
    """
    Asynchronous payment processor with queue-based processing
    """

    def __init__(self, db_path: str = 'payment_processing.db'):
        self.db_path = db_path
        self.setup_database()
        self.job_queue = Queue(maxsize=1000)
        self.dead_letter_queue = Queue(maxsize=100)
        self.running = False
        self.worker_thread = None

        # Metrics
        self.metrics = {
            'total_jobs': 0,
            'successful_jobs': 0,
            'failed_jobs': 0,
            'queue_size': 0,
            'processing_time': []
        }
        self.metrics_lock = threading.Lock()

    def setup_database(self):
        """Initialize SQLite database for payment tracking"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payment_jobs (
                    job_id TEXT PRIMARY KEY,
                    booking_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payment_id TEXT,
                    transaction_id TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    retries INTEGER DEFAULT 0,
                    last_attempt TEXT
                )
            ''')

            # Create index for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_booking_id ON payment_jobs(booking_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON payment_jobs(status)')

            conn.commit()

    def _log_job_metrics(self, job: PaymentJob, response: PaymentResponse):
        """Log job processing metrics"""
        with self.metrics_lock:
            self.metrics['total_jobs'] += 1
            self.metrics['queue_size'] = self.job_queue.qsize()

            if response.status == PaymentStatus.COMPLETED:
                self.metrics['successful_jobs'] += 1
            else:
                self.metrics['failed_jobs'] += 1

            if response.status == PaymentStatus.COMPLETED:
                processing_time = time.time() - datetime.fromisoformat(job.created_at).timestamp()
                self.metrics['processing_time'].append(processing_time)

    def _save_job_to_db(self, job: PaymentJob, response: PaymentResponse):
        """Save job status to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO payment_jobs (
                    job_id, booking_id, customer_id, amount, currency, payment_method,
                    status, payment_id, transaction_id, error_code, error_message,
                    created_at, updated_at, retries, last_attempt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job.job_id,
                job.payment_request.booking_id,
                job.payment_request.customer_id,
                job.payment_request.amount,
                job.payment_request.currency,
                job.payment_request.payment_method.value,
                response.status.value,
                response.payment_id,
                response.transaction_id,
                response.error_code,
                response.error_message,
                job.created_at,
                datetime.utcnow().isoformat(),
                job.retries,
                job.last_attempt
            ))

            conn.commit()

    def _process_job(self, job: PaymentJob) -> PaymentResponse:
        """Process a single payment job"""
        try:
            # Create payment intent
            response = gateway.create_payment_intent(job.payment_request)

            # If payment intent created successfully, confirm it
            if response.status == PaymentStatus.PROCESSING:
                confirm_response = gateway.confirm_payment(response.payment_id)
                response = confirm_response

            # Log metrics
            self._log_job_metrics(job, response)

            # Save to database
            self._save_job_to_db(job, response)

            return response

        except Exception as e:
            error_response = PaymentResponse(
                payment_id=str(job.job_id),
                status=PaymentStatus.FAILED,
                amount=job.payment_request.amount,
                currency=job.payment_request.currency,
                error_code="PROCESSING_ERROR",
                error_message=str(e)
            )

            # Save failed job to database
            self._save_job_to_db(job, error_response)

            return error_response

    def _worker(self):
        """Worker thread that processes jobs from the queue"""
        while self.running:
            try:
                job = self.job_queue.get(timeout=5)

                start_time = time.time()
                logger.info(f"Processing payment job {job.job_id} for booking {job.payment_request.booking_id}")

                response = self._process_job(job)

                if response.status == PaymentStatus.COMPLETED:
                    logger.info(f"Successfully processed payment job {job.job_id}")
                else:
                    logger.warning(f"Payment job {job.job_id} failed: {response.error_message}")

                    # Retry logic
                    if job.retries < 3:
                        job.retries += 1
                        job.last_attempt = datetime.utcnow().isoformat()
                        self.job_queue.put(job)
                        logger.info(f"Retrying job {job.job_id} (attempt {job.retries})")
                    else:
                        # Move to dead letter queue after max retries
                        self.dead_letter_queue.put(job)
                        logger.error(f"Job {job.job_id} moved to dead letter queue after {job.retries} retries")

                self.job_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in worker thread: {str(e)}")
                time.sleep(1)

    def start(self):
        """Start the payment processor"""
        if self.running:
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        logger.info("Payment processor started")

    def stop(self):
        """Stop the payment processor"""
        if not self.running:
            return

        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)

        logger.info("Payment processor stopped")

    def enqueue_payment(self, payment_request: PaymentRequest) -> str:
        """Add a payment job to the queue"""
        job_id = str(int(time.time() * 1000))
        job = PaymentJob(job_id=job_id, payment_request=payment_request)

        # Save initial job to database
        self._save_job_to_db(job, PaymentResponse(
            payment_id=job_id,
            status=PaymentStatus.PENDING,
            amount=payment_request.amount,
            currency=payment_request.currency
        ))

        self.job_queue.put(job)
        logger.info(f"Enqueued payment job {job_id} for booking {payment_request.booking_id}")

        return job_id

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a payment job"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM payment_jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()

            if row:
                columns = ['job_id', 'booking_id', 'customer_id', 'amount', 'currency',
                          'payment_method', 'status', 'payment_id', 'transaction_id',
                          'error_code', 'error_message', 'created_at', 'updated_at',
                          'retries', 'last_attempt']
                return dict(zip(columns, row))

        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get current processor metrics"""
        with self.metrics_lock:
            return {
                'total_jobs': self.metrics['total_jobs'],
                'successful_jobs': self.metrics['successful_jobs'],
                'failed_jobs': self.metrics['failed_jobs'],
                'success_rate': self.metrics['successful_jobs'] / max(self.metrics['total_jobs'], 1),
                'average_processing_time': round(
                    sum(self.metrics['processing_time']) / max(len(self.metrics['processing_time']), 1),
                    4
                ) if self.metrics['processing_time'] else 0,
                'queue_size': self.metrics['queue_size'],
                'dead_letter_queue_size': self.dead_letter_queue.qsize(),
                'timestamp': datetime.utcnow().isoformat()
            }

# Global processor instance
processor = PaymentProcessor()

def start_payment_processor():
    """Start the global payment processor"""
    processor.start()
    return processor
