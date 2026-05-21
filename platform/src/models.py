"""
Cassandra data models for award availability.
Optimized for write-heavy workload with time-series partitioning.
"""

from cassandra.cqlengine import columns, models
from cassandra.cqlengine import indexes
from datetime import datetime
from typing import Optional
import uuid

class BaseModel(models.Model):
    """Base model with common fields and methods."""
    __abstract__ = True

    id = columns.UUID(primary_key=True, default=uuid.uuid4)
    created_at = columns.DateTime(required=True, default=datetime.utcnow)
    updated_at = columns.DateTime(required=True, default=datetime.utcnow)

    def save(self, *args, **kwargs):
        """Override save to update timestamp."""
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

class FlightAward(BaseModel):
    """Flight award availability model."""
    __keyspace__ = 'award_availability'
    __table_name__ = 'flight_awards'

    # Partition key
    departure_date = columns.Date(required=True)
    origin = columns.Text(required=True, index=True)
    destination = columns.Text(required=True, index=True)

    # Clustering columns
    award_id = columns.UUID(required=True, primary_key=True, clustering_order="DESC")
    flight_number = columns.Text(required=True)
    cabin_class = columns.Text(required=True)
    airline_iata = columns.Text(required=True)

    # Data fields
    status = columns.Text(required=True)
    points_required = columns.Integer()
    cash_required = columns.Float()
    total_price = columns.Float()
    currency = columns.Text(default="USD")
    departure_time = columns.DateTime()
    arrival_time = columns.DateTime()
    flight_duration = columns.Integer()
    operating_airline = columns.Text()
    marketing_airline = columns.Text()
    source = columns.Text(required=True)
    metadata = columns.Map(columns.Text, columns.Text)

    # Secondary indexes for common queries
    indexes = {
        indexes.Index(columns=('departure_date', 'origin', 'destination', 'cabin_class')),
        indexes.Index(columns=('airline_iata', 'departure_date')),
        indexes.Index(columns=('status', 'departure_date')),
    }

class HotelAward(BaseModel):
    """Hotel award availability model."""
    __keyspace__ = 'award_availability'
    __table_name__ = 'hotel_awards'

    # Partition key
    check_in_date = columns.Date(required=True)
    property_id = columns.Text(required=True, index=True)

    # Clustering columns
    award_id = columns.UUID(primary_key=True, clustering_order="DESC")
    nights = columns.Integer()
    room_type = columns.Text()

    # Data fields
    status = columns.Text(required=True)
    points_required = columns.Integer()
    cash_required = columns.Float()
    total_price = columns.Float()
    currency = columns.Text(default="USD")
    source = columns.Text(required=True)
    metadata = columns.Map(columns.Text, columns.Text)

    # Secondary indexes
    indexes = {
        indexes.Index(columns=('property_id', 'check_in_date')),
        indexes.Index(columns=('status', 'check_in_date')),
    }

class CarAward(BaseModel):
    """Car award availability model."""
    __keyspace__ = 'award_availability'
    __table_name__ = 'car_awards'

    # Partition key
    pickup_date = columns.Date(required=True)
    pickup_location = columns.Text(required=True, index=True)

    # Clustering columns
    award_id = columns.UUID(primary_key=True, clustering_order="DESC")
    vehicle_id = columns.Text()

    # Data fields
    status = columns.Text(required=True)
    points_required = columns.Integer()
    cash_required = columns.Float()
    total_price = columns.Float()
    currency = columns.Text(default="USD")
    source = columns.Text(required=True)
    metadata = columns.Map(columns.Text, columns.Text)

    # Secondary indexes
    indexes = {
        indexes.Index(columns=('pickup_location', 'pickup_date')),
        indexes.Index(columns=('status', 'pickup_date')),
    }

class AwardMetadata(models.Model):
    """Metadata about award sources and processing."""
    __keyspace__ = 'award_availability'
    __table_name__ = 'award_metadata'

    source = columns.Text(primary_key=True)
    last_updated = columns.DateTime(required=True)
    records_processed = columns.Counter()
    records_failed = columns.Counter()
    last_successful_sync = columns.DateTime()
    next_sync_scheduled = columns.DateTime()
    status = columns.Text()
    version = columns.Text()
    metadata = columns.Map(columns.Text, columns.Text)
