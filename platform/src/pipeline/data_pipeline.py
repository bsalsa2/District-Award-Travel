"""
District Award Travel - Data Pipeline for Award Recommendation Engine
ETL pipeline for collecting, cleaning, and preparing data for ML models
"""

import os
import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AwardTravelDataPipeline:
    """
    End-to-end data pipeline for District Award Travel.
    Handles data collection, cleaning, transformation, and feature engineering.
    """

    def __init__(self, db_path: str = "platform/data/award_travel.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database schema if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)

            # Clients table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                age INTEGER,
                membership_tier TEXT CHECK(membership_tier IN ('bronze', 'silver', 'gold', 'platinum')),
                total_points_balance INTEGER DEFAULT 0,
                days_since_last_booking INTEGER DEFAULT 0,
                avg_nights_per_booking REAL DEFAULT 0,
                total_bookings INTEGER DEFAULT 0,
                preferred_destination_region TEXT,
                preferred_award_type TEXT,
                travel_frequency TEXT CHECK(travel_frequency IN ('monthly', 'quarterly', 'biannually', 'annually')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Awards table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS awards (
                award_id TEXT PRIMARY KEY,
                award_type TEXT NOT NULL CHECK(award_type IN ('flight', 'hotel', 'package', 'experience')),
                destination TEXT NOT NULL,
                region TEXT NOT NULL,
                partner_airline TEXT,
                point_cost INTEGER NOT NULL,
                seasonality_score REAL CHECK(seasonality_score BETWEEN 0 AND 1),
                availability_score REAL CHECK(availability_score BETWEEN 0 AND 1),
                description TEXT,
                min_nights INTEGER DEFAULT 1,
                max_nights INTEGER DEFAULT 30,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Bookings table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                award_id TEXT NOT NULL,
                booking_date TIMESTAMP NOT NULL,
                nights INTEGER NOT NULL,
                points_used INTEGER NOT NULL,
                redemption_success BOOLEAN,
                FOREIGN KEY (client_id) REFERENCES clients(client_id),
                FOREIGN KEY (award_id) REFERENCES awards(award_id)
            )
            """)

            # Recommendations table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                award_id TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                model_used TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_clicked BOOLEAN DEFAULT FALSE,
                clicked_at TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(client_id),
                FOREIGN KEY (award_id) REFERENCES awards(award_id)
            )
            """)

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_client ON bookings(client_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_award ON bookings(award_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_client ON recommendations(client_id)")

            conn.commit()
            conn.close()

            logger.info("Database schema initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def load_sample_data(self):
        """Load sample data for development and testing"""
        try:
            conn = sqlite3.connect(self.db_path)

            # Sample clients
            clients = [
                ('CLIENT-001', 'John Smith', 'john.smith@email.com', 35, 'gold', 150000, 90, 7, 12, 'europe', 'flight', 'quarterly'),
                ('CLIENT-002', 'Sarah Johnson', 'sarah.j@email.com', 42, 'platinum', 250000, 30, 10, 25, 'asia', 'hotel', 'monthly'),
                ('CLIENT-003', 'Mike Davis', 'mike.d@email.com', 28, 'silver', 80000, 180, 5, 8, 'north america', 'package', 'biannually'),
                ('CLIENT-004', 'Emily Chen', 'emily.c@email.com', 55, 'gold', 120000, 60, 14, 18, 'europe', 'flight', 'annually'),
                ('CLIENT-005', 'Robert Wilson', 'robert.w@email.com', 31, 'bronze', 50000, 270, 3, 4, 'south america', 'experience', 'biannually')
            ]

            conn.executemany("""
            INSERT OR IGNORE INTO clients
            (client_id, name, email, age, membership_tier, total_points_balance,
             days_since_last_booking, avg_nights_per_booking, total_bookings,
             preferred_destination_region, preferred_award_type, travel_frequency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, clients)

            # Sample awards
            awards = [
                ('AWARD-001', 'flight', 'Paris, France', 'europe', 'Air France', 85000, 0.85, 0.92,
                 'Round trip business class to Paris from NYC', 5, 14),
                ('AWARD-002', 'hotel', 'Tokyo, Japan', 'asia', 'Marriott', 120000, 0.78, 0.88,
                 '5 nights at luxury Tokyo hotel', 5, 10),
                ('AWARD-003', 'package', 'Bali, Indonesia', 'asia', 'Expedia', 95000, 0.92, 0.85,
                 '7 nights all-inclusive Bali resort', 7, 14),
                ('AWARD-004', 'flight', 'Sydney, Australia', 'oceania', 'Qantas', 110000, 0.65, 0.95,
                 'Round trip premium economy to Sydney', 7, 21),
                ('AWARD-005', 'experience', 'Rome, Italy', 'europe', None, 75000, 0.95, 0.90,
                 'Vatican tours and Colosseum experience', 3, 5),
                ('AWARD-006', 'hotel', 'New York City, USA', 'north america', 'Hilton', 60000, 0.88, 0.98,
                 '3 nights luxury NYC hotel', 3, 7),
                ('AWARD-007', 'flight', 'London, UK', 'europe', 'British Airways', 70000, 0.82, 0.94,
                 'Round trip business class to London', 4, 10),
                ('AWARD-008', 'package', 'Santorini, Greece', 'europe', 'Marriott', 105000, 0.90, 0.80,
                 '7 nights luxury Santorini resort', 7, 14)
            ]

            conn.executemany("""
            INSERT OR IGNORE INTO awards
            (award_id, award_type, destination, region, partner_airline, point_cost,
             seasonality_score, availability_score, description, min_nights, max_nights)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, awards)

            # Sample bookings
            bookings = [
                ('CLIENT-001', 'AWARD-001', '2024-01-15 10:30:00', 7, 85000, True),
                ('CLIENT-001', 'AWARD-007', '2024-03-20 14:00:00', 5, 70000, True),
                ('CLIENT-002', 'AWARD-002', '2024-02-10 09:15:00', 8, 120000, True),
                ('CLIENT-002', 'AWARD-003', '2024-04-05 16:45:00', 10, 95000, True),
                ('CLIENT-003', 'AWARD-006', '2024-01-05 11:20:00', 4, 60000, True),
                ('CLIENT-004', 'AWARD-001', '2024-02-28 13:30:00', 7, 85000, True),
                ('CLIENT-005', 'AWARD-005', '2024-03-15 12:00:00', 3, 75000, False)
            ]

            conn.executemany("""
            INSERT OR IGNORE INTO bookings
            (client_id, award_id, booking_date, nights, points_used, redemption_success)
            VALUES (?, ?, ?, ?, ?, ?)
            """, bookings)

            conn.commit()
            conn.close()

            logger.info("Sample data loaded successfully")

        except Exception as e:
            logger.error(f"Error loading sample data: {e}")
            raise

    def collect_client_interactions(self, client_id: str, interactions: List[Dict]):
        """
        Collect and store client interactions with recommendations
        Args:
            client_id: Client identifier
            interactions: List of interaction dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)

            for interaction in interactions:
                conn.execute("""
                INSERT INTO recommendations
                (client_id, award_id, confidence_score, model_used, is_clicked, clicked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    client_id,
                    interaction['award_id'],
                    interaction['confidence_score'],
                    interaction['model_used'],
                    interaction.get('is_clicked', False),
                    interaction.get('clicked_at', None)
                ))

            conn.commit()
            conn.close()
            logger.info(f"Stored {len(interactions)} interactions for client {client_id}")

        except Exception as e:
            logger.error(f"Error storing client interactions: {e}")
            raise

    def update_client_points(self, client_id: str, points_change: int, reason: str):
        """
        Update client's point balance
        Args:
            client_id: Client identifier
            points_change: Amount to add/subtract (can be negative)
            reason: Reason for points change (e.g., 'booking', 'expiration', 'adjustment')
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Get current balance
            current_balance = conn.execute(
                "SELECT total_points_balance FROM clients WHERE client_id = ?",
                (client_id,)
            ).fetchone()

            if current_balance is None:
                logger.warning(f"Client {client_id} not found")
                return False

            new_balance = max(0, current_balance[0] + points_change)

            # Update balance
            conn.execute("""
            UPDATE clients
            SET total_points_balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
            """, (new_balance, client_id))

            # Log the change
            conn.execute("""
            INSERT INTO points_history
            (client_id, points_change, new_balance, reason, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (client_id, points_change, new_balance, reason))

            conn.commit()
            conn.close()
            logger.info(f"Updated points for {client_id}: {points_change} ({reason})")

            return True

        except Exception as e:
            logger.error(f"Error updating client points: {e}")
            raise

    def generate_client_features(self, client_id: str) -> Dict:
        """
        Generate feature vector for a client
        Returns dictionary of features for ML model input
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Get client data
            client = conn.execute(
                "SELECT * FROM clients WHERE client_id = ?",
                (client_id,)
            ).fetchone()

            if client is None:
                logger.warning(f"Client {client_id} not found")
                return None

            # Get recent booking statistics
            recent_bookings = conn.execute("""
            SELECT nights, points_used, booking_date
            FROM bookings
            WHERE client_id = ?
            ORDER BY booking_date DESC
            LIMIT 5
            """, (client_id,)).fetchall()

            # Calculate features
            features = {
                'client_id': client[0],
                'client_age': client[3],
                'total_points_balance': client[5],
                'days_since_last_booking': client[6],
                'avg_nights_per_booking': client[7],
                'total_bookings': client[8],
                'membership_tier': client[4],
                'preferred_destination_region': client[9],
                'preferred_award_type': client[10],
                'travel_frequency': client[11],
                'recent_avg_nights': sum(b[0] for b in recent_bookings) / len(recent_bookings) if recent_bookings else 0,
                'recent_avg_points': sum(b[1] for b in recent_bookings) / len(recent_bookings) if recent_bookings else 0,
                'booking_frequency': len(recent_bookings) / max(1, (datetime.now() - datetime.strptime(client[13], '%Y-%m-%d %H:%M:%S')).days / 30)
            }

            conn.close()
            return features

        except Exception as e:
            logger.error(f"Error generating client features: {e}")
            raise

    def get_awards_for_recommendation(self, limit: int = 100) -> List[Dict]:
        """Get active awards suitable for recommendation"""
        try:
            conn = sqlite3.connect(self.db_path)

            awards = conn.execute("""
            SELECT award_id, award_type, destination, region, partner_airline,
                   point_cost, seasonality_score, availability_score
            FROM awards
            WHERE is_active = TRUE
            ORDER BY availability_score DESC, seasonality_score DESC
            LIMIT ?
            """, (limit,)).fetchall()

            conn.close()

            return [{
                'award_id': award[0],
                'award_type': award[1],
                'destination': award[2],
                'region': award[3],
                'partner_airline': award[4],
                'point_cost': award[5],
                'seasonality_score': award[6],
                'availability_score': award[7]
            } for award in awards]

        except Exception as e:
            logger.error(f"Error fetching awards: {e}")
            raise

    def calculate_model_metrics(self) -> Dict:
        """Calculate performance metrics for recommendation models"""
        try:
            conn = sqlite3.connect(self.db_path)

            # Get recent recommendations and outcomes
            data = conn.execute("""
            SELECT r.award_id, r.confidence_score, r.model_used,
                   b.redemption_success
            FROM recommendations r
            JOIN bookings b ON r.client_id = b.client_id AND r.award_id = b.award_id
            WHERE b.redemption_success IS NOT NULL
            AND r.generated_at > datetime('now', '-30 days')
            """).fetchall()

            conn.close()

            if not data:
                return {'message': 'Insufficient data for metrics calculation'}

            # Calculate metrics by model
            results = {}
            for model in set(row[2] for row in data):
                model_data = [row for row in data if row[2] == model]
                scores = [row[1] for row in model_data]
                successes = [row[3] for row in model_data]

                # Simple correlation between confidence and success
                correlation = np.corrcoef(scores, successes)[0, 1]

                results[model] = {
                    'sample_size': len(model_data),
                    'avg_confidence': float(np.mean(scores)),
                    'success_rate': float(np.mean(successes)),
                    'confidence_success_correlation': float(correlation),
                    'top_5_avg_confidence': float(np.mean(sorted(scores, reverse=True)[:5])),
                    'top_5_success_rate': float(np.mean(successes[:5] if len(successes) >= 5 else successes))
                }

            return results

        except Exception as e:
            logger.error(f"Error calculating model metrics: {e}")
            raise

# Singleton instance
data_pipeline = AwardTravelDataPipeline()

if __name__ == "__main__":
    # Example usage
    pipeline = AwardTravelDataPipeline()

    # Initialize database and load sample data
    pipeline._initialize_database()
    pipeline.load_sample_data()

    # Test feature generation
    features = pipeline.generate_client_features('CLIENT-001')
    print("Client Features:")
    print(json.dumps(features, indent=2))

    # Get awards for recommendation
    awards = pipeline.get_awards_for_recommendation(limit=10)
    print("\nSample Awards:")
    for award in awards[:5]:
        print(f"{award['destination']} - {award['point_cost']} points")

    # Calculate model metrics
    metrics = pipeline.calculate_model_metrics()
    print("\nModel Metrics:")
    print(json.dumps(metrics, indent=2))
