"""
Unit tests for redemption tracking pipeline.
"""

import unittest
import tempfile
import os
import json
from datetime import datetime
from platform.src.pipelines.redemption_tracking import (
    RedemptionRecord,
    RedemptionValidator,
    RedemptionPipelineOptions
)
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

class TestRedemptionPipeline(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        # Sample test data
        self.valid_redemption = {
            "client_id": "CLIENT123",
            "booking_reference": "BK789XYZ",
            "points_used": 50000,
            "award_type": "flight",
            "redemption_date": "2024-01-15T10:30:00Z",
            "flight_details": {
                "flight_number": "AA123",
                "departure_airport": "JFK",
                "arrival_airport": "LAX",
                "departure_date": "2024-03-20",
                "cabin_class": "business"
            },
            "status": "completed"
        }

        self.invalid_redemption = {
            "client_id": "",
            "booking_reference": "BK789XYZ",
            "points_used": -1000,
            "award_type": "flight"
        }

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)

    def test_redemption_record_creation(self):
        """Test RedemptionRecord creation and validation."""
        record = RedemptionRecord(
            client_id="CLIENT123",
            booking_reference="BK789XYZ",
            award_type="flight",
            points_used=50000,
            redemption_date="2024-01-15T10:30:00Z",
            flight_details={"flight_number": "AA123"},
            status="completed",
            redemption_id="abc123"
        )

        self.assertEqual(record.client_id, "CLIENT123")
        self.assertEqual(record.points_used, 50000)
        self.assertEqual(record.award_type, "flight")

    def test_redemption_record_validation_fails_on_empty_client_id(self):
        """Test that empty client_id raises validation error."""
        with self.assertRaises(ValueError):
            RedemptionRecord(
                client_id="",
                booking_reference="BK789XYZ",
                award_type="flight",
                points_used=50000,
                redemption_date="2024-01-15T10:30:00Z",
                flight_details={},
                status="completed",
                redemption_id="abc123"
            )

    def test_redemption_record_validation_fails_on_negative_points(self):
        """Test that negative points raises validation error."""
        with self.assertRaises(ValueError):
            RedemptionRecord(
                client_id="CLIENT123",
                booking_reference="BK789XYZ",
                award_type="flight",
                points_used=-50000,
                redemption_date="2024-01-15T10:30:00Z",
                flight_details={},
                status="completed",
                redemption_id="abc123"
            )

    def test_redemption_validator_processes_valid_record(self):
        """Test that validator processes valid records correctly."""
        validator = RedemptionValidator({})

        with TestPipeline() as p:
            result = (
                p
                | beam.Create([self.valid_redemption])
                | beam.ParDo(validator)
            )

            assert_that(result, equal_to([
                RedemptionRecord(
                    client_id="CLIENT123",
                    booking_reference="BK789XYZ",
                    award_type="flight",
                    points_used=50000,
                    redemption_date="2024-01-15T10:30:00Z",
                    flight_details=self.valid_redemption["flight_details"],
                    status="completed",
                    redemption_id=validator._generate_redemption_id(self.valid_redemption)
                )
            ]))

    def test_redemption_validator_filters_invalid_record(self):
        """Test that validator filters out invalid records."""
        validator = RedemptionValidator({})

        with TestPipeline() as p:
            result = (
                p
                | beam.Create([self.valid_redemption, self.invalid_redemption])
                | beam.ParDo(validator)
            )

            # Should only yield the valid record
            assert_that(result, equal_to([
                RedemptionRecord(
                    client_id="CLIENT123",
                    booking_reference="BK789XYZ",
                    award_type="flight",
                    points_used=50000,
                    redemption_date="2024-01-15T10:30:00Z",
                    flight_details=self.valid_redemption["flight_details"],
                    status="completed",
                    redemption_id=validator._generate_redemption_id(self.valid_redemption)
                )
            ]))

    def test_redemption_id_generation(self):
        """Test that redemption IDs are generated consistently."""
        validator = RedemptionValidator({})

        record1 = validator._generate_redemption_id(self.valid_redemption)
        record2 = validator._generate_redemption_id(self.valid_redemption)

        self.assertEqual(record1, record2)
        self.assertEqual(len(record1), 16)  # SHA256 truncated to 16 chars

        # Different record should generate different ID
        different_record = self.valid_redemption.copy()
        different_record["points_used"] = 75000
        record3 = validator._generate_redemption_id(different_record)

        self.assertNotEqual(record1, record3)

    def test_sqlite_writer_creates_table(self):
        """Test that SQLite writer creates the required tables."""
        from platform.src.pipelines.redemption_tracking import SQLiteBatchWriter

        writer = SQLiteBatchWriter(self.test_db.name, batch_size=10)

        writer.setup()
        writer._create_tables()
        writer.teardown()

        # Verify table was created
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='redemptions'")
        table_exists = cursor.fetchone() is not None

        self.assertTrue(table_exists)
        conn.close()

    def test_pipeline_options_parsing(self):
        """Test that pipeline options are parsed correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        options = RedemptionPipelineOptions()
        options._add_argparse_args(parser)

        args = parser.parse_args([
            '--input', 'test_input.json',
            '--output', 'test_output.db',
            '--batch_size', '500'
        ])

        self.assertEqual(args.input, 'test_input.json')
        self.assertEqual(args.output, 'test_output.db')
        self.assertEqual(args.batch_size, 500)

if __name__ == '__main__':
    unittest.main()
