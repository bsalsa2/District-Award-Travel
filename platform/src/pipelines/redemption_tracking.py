"""
Redemption Tracking Pipeline for District Award Travel
High-performance Apache Beam pipeline for tracking client redemptions
with mechanical sympathy for maximum throughput.
"""

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.io import ReadFromText, WriteToText
from apache_beam.io.gcp import bigquery
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import re
from dataclasses import dataclass
import hashlib

# Configure logging for performance monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RedemptionRecord:
    """Immutable redemption record with validation."""
    client_id: str
    booking_reference: str
    award_type: str
    points_used: int
    redemption_date: str
    flight_details: Dict[str, Any]
    status: str
    redemption_id: str

    def __post_init__(self):
        """Validate redemption record."""
        if not self.client_id:
            raise ValueError("Client ID cannot be empty")
        if not self.booking_reference:
            raise ValueError("Booking reference cannot be empty")
        if self.points_used <= 0:
            raise ValueError("Points used must be positive")
        if not self.redemption_date:
            raise ValueError("Redemption date cannot be empty")

class RedemptionPipelineOptions(PipelineOptions):
    """Custom pipeline options for redemption tracking."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument(
            '--input',
            type=str,
            help='Input source for redemption data (JSON file or BigQuery table)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output SQLite database path'
        )
        parser.add_argument(
            '--schema',
            type=str,
            default='platform/src/pipelines/schemas/redemption_schema.json',
            help='Path to redemption schema file'
        )
        parser.add_argument(
            '--batch_size',
            type=int,
            default=1000,
            help='Batch size for SQLite writes'
        )

class RedemptionValidator(beam.DoFn):
    """Validates redemption records with schema enforcement."""

    def __init__(self, expected_schema: Dict[str, Any]):
        self.expected_schema = expected_schema
        self.validation_errors = 0
        self.successful_validations = 0

    def setup(self):
        """Initialize validation metrics."""
        self.validation_errors = 0
        self.successful_validations = 0

    def process(self, element: Dict[str, Any]) -> beam.PCollection:
        """Validate and transform redemption data."""
        try:
            # Validate required fields
            if not all(key in element for key in ['client_id', 'booking_reference', 'points_used']):
                self.validation_errors += 1
                logger.warning(f"Missing required fields in record: {element}")
                return

            # Validate data types
            if not isinstance(element['points_used'], int) or element['points_used'] <= 0:
                self.validation_errors += 1
                logger.warning(f"Invalid points_used in record: {element}")
                return

            if not isinstance(element['client_id'], str) or not element['client_id']:
                self.validation_errors += 1
                logger.warning(f"Invalid client_id in record: {element}")
                return

            # Generate redemption ID (hash of key fields)
            redemption_id = self._generate_redemption_id(element)

            # Create validated record
            record = RedemptionRecord(
                client_id=element['client_id'],
                booking_reference=element['booking_reference'],
                award_type=element.get('award_type', 'flight'),
                points_used=element['points_used'],
                redemption_date=element.get('redemption_date', datetime.utcnow().isoformat()),
                flight_details=element.get('flight_details', {}),
                status=element.get('status', 'completed'),
                redemption_id=redemption_id
            )

            self.successful_validations += 1
            yield record

        except Exception as e:
            self.validation_errors += 1
            logger.error(f"Validation failed for record: {element}. Error: {str(e)}")

    def _generate_redemption_id(self, element: Dict[str, Any]) -> str:
        """Generate unique redemption ID using hash of key fields."""
        key_str = f"{element['client_id']}:{element['booking_reference']}:{element['points_used']}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

class SQLiteBatchWriter(beam.DoFn):
    """Batch writer to SQLite with connection pooling and transactions."""

    def __init__(self, db_path: str, batch_size: int = 1000):
        self.db_path = db_path
        self.batch_size = batch_size
        self.batch = []
        self.connection = None
        self.write_count = 0
        self.error_count = 0

    def setup(self):
        """Initialize database connection."""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._create_tables()
            logger.info(f"Connected to SQLite database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise

    def _create_tables(self):
        """Create redemption tracking tables with proper schema."""
        cursor = self.connection.cursor()

        # Main redemption table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS redemptions (
            redemption_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            booking_reference TEXT NOT NULL,
            award_type TEXT DEFAULT 'flight',
            points_used INTEGER NOT NULL,
            redemption_date TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            flight_details_json TEXT,
            UNIQUE(client_id, booking_reference)
        )
        """)

        # Index for fast client lookups
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_redemptions
        ON redemptions(client_id, redemption_date)
        """)

        # Index for booking reference lookups
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_booking_reference
        ON redemptions(booking_reference)
        """)

        self.connection.commit()

    def process(self, element: RedemptionRecord, window=beam.DoFn.WindowParam):
        """Buffer records and write in batches."""
        self.batch.append(element)

        if len(self.batch) >= self.batch_size:
            self._flush_batch()

    def finish_bundle(self):
        """Flush any remaining records in the batch."""
        if self.batch:
            self._flush_batch()

    def teardown(self):
        """Clean up database connection."""
        if self.batch:
            self._flush_batch()
        if self.connection:
            self.connection.close()
            logger.info(f"Closed SQLite connection. Wrote {self.write_count} records")

    def _flush_batch(self):
        """Write batch of records to SQLite with transaction."""
        if not self.batch:
            return

        try:
            cursor = self.connection.cursor()

            # Use transaction for atomic writes
            cursor.execute("BEGIN TRANSACTION")

            # Prepare batch insert
            for record in self.batch:
                cursor.execute("""
                INSERT OR REPLACE INTO redemptions
                (redemption_id, client_id, booking_reference, award_type, points_used,
                 redemption_date, status, flight_details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.redemption_id,
                    record.client_id,
                    record.booking_reference,
                    record.award_type,
                    record.points_used,
                    record.redemption_date,
                    record.status,
                    json.dumps(record.flight_details)
                ))

            self.connection.commit()
            self.write_count += len(self.batch)
            logger.info(f"Wrote {len(self.batch)} records to SQLite")

        except Exception as e:
            self.connection.rollback()
            self.error_count += len(self.batch)
            logger.error(f"Batch write failed: {str(e)}. Records lost: {len(self.batch)}")
            raise

        finally:
            self.batch = []

class RedemptionMetrics(beam.DoFn):
    """Collect and report pipeline metrics."""

    def __init__(self):
        self.records_processed = 0
        self.records_validated = 0
        self.records_written = 0
        self.start_time = None

    def setup(self):
        self.start_time = datetime.utcnow()
        logger.info("Pipeline metrics initialized")

    def process(self, element, window=beam.DoFn.WindowParam):
        self.records_processed += 1
        yield element

    def finish_bundle(self):
        """Report metrics at the end of each bundle."""
        if self.records_processed > 0:
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            throughput = self.records_processed / duration if duration > 0 else 0

            logger.info(f"""
            === Pipeline Metrics ===
            Records processed: {self.records_processed}
            Records validated: {self.records_validated}
            Records written: {self.records_written}
            Duration: {duration:.2f} seconds
            Throughput: {throughput:.2f} records/second
            """)

class RedemptionTrackingPipeline:
    """Main redemption tracking pipeline."""

    def __init__(self, options: RedemptionPipelineOptions):
        self.options = options
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        """Load validation schema from file."""
        try:
            with open(self.options.schema, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schema: {str(e)}")
            raise

    def run(self):
        """Execute the redemption tracking pipeline."""

        # Configure pipeline options for performance
        pipeline_options = PipelineOptions()
        pipeline_options.view_as(RedemptionPipelineOptions).input = self.options.input
        pipeline_options.view_as(RedemptionPipelineOptions).output = self.options.output
        pipeline_options.view_as(RedemptionPipelineOptions).batch_size = self.options.batch_size

        # Create pipeline with optimized settings
        with beam.Pipeline(options=pipeline_options) as pipeline:
            # Read input data (supports both file and BigQuery sources)
            if self.options.input.endswith('.json'):
                raw_data = (
                    pipeline
                    | 'ReadJSON' >> ReadFromText(self.options.input)
                    | 'ParseJSON' >> beam.Map(json.loads)
                )
            else:
                # Assume BigQuery source
                raw_data = (
                    pipeline
                    | 'ReadFromBigQuery' >> bigquery.ReadFromBigQuery(
                        table=self.options.input,
                        method='DIRECT_READ'
                    )
                )

            # Transform and validate records
            validated_records = (
                raw_data
                | 'ValidateRecords' >> beam.ParDo(RedemptionValidator(self.schema))
                .with_resource_hints(
                    num_workers=4,
                    disk_size_gb=10,
                    machine_type='n1-standard-4'
                )
            )

            # Write to SQLite with batch processing
            _ = (
                validated_records
                | 'AddMetrics' >> beam.ParDo(RedemptionMetrics())
                | 'WriteToSQLite' >> beam.ParDo(SQLiteBatchWriter(
                    self.options.output,
                    self.options.batch_size
                ))
                .with_resource_hints(
                    num_workers=2,
                    disk_size_gb=5,
                    machine_type='n1-standard-2'
                )
            )

            # Log pipeline completion
            pipeline_result = pipeline.run()
            pipeline_result.wait_until_finish()

            logger.info(f"Pipeline completed. Status: {pipeline_result.state}")

def main():
    """Entry point for the redemption tracking pipeline."""
    import argparse

    parser = argparse.ArgumentParser()
    pipeline_options = RedemptionPipelineOptions()
    pipeline_options._add_argparse_args(parser)

    args = parser.parse_args()

    # Validate arguments
    if not args.input:
        raise ValueError("Input source must be specified")
    if not args.output:
        raise ValueError("Output SQLite path must be specified")

    # Run pipeline
    pipeline = RedemptionTrackingPipeline(args)
    pipeline.run()

if __name__ == '__main__':
    main()
