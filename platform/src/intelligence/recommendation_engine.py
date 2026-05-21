"""
District Award Travel - AI-Powered Award Recommendation Engine
Core recommendation system using TensorFlow and scikit-learn
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
import joblib
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('recommendation_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AwardRecommendationEngine:
    """
    AI-powered award recommendation engine for District Award Travel.
    Uses hybrid approach: Random Forest for feature importance + Neural Network for pattern recognition.
    """

    def __init__(self, db_path: str = "platform/data/award_travel.db"):
        self.db_path = db_path
        self.models_dir = Path("platform/models")
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Initialize models
        self.feature_processor = None
        self.random_forest_model = None
        self.neural_model = None
        self.scaler = None
        self.encoder = None

        # Load or initialize models
        self._initialize_models()

    def _initialize_models(self):
        """Initialize or load existing models"""
        try:
            # Try to load existing models
            self.random_forest_model = joblib.load(self.models_dir / "random_forest_model.pkl")
            self.neural_model = load_model(self.models_dir / "neural_model.h5")
            self.scaler = joblib.load(self.models_dir / "scaler.pkl")
            self.encoder = joblib.load(self.models_dir / "encoder.pkl")
            logger.info("Loaded existing models from disk")
        except FileNotFoundError:
            logger.info("No existing models found. Initializing new models.")
            self._create_feature_processor()
            self._create_random_forest_model()
            self._create_neural_model()

    def _create_feature_processor(self):
        """Create feature preprocessing pipeline"""
        numeric_features = ['client_age', 'total_points_balance', 'days_since_last_booking',
                           'avg_nights_per_booking', 'total_bookings']
        categorical_features = ['membership_tier', 'preferred_destination_region',
                               'preferred_award_type', 'travel_frequency']

        self.feature_processor = ColumnTransformer(
            transformers=[
                ('num', StandardScaler(), numeric_features),
                ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
            ])

    def _create_random_forest_model(self):
        """Create Random Forest model for feature importance and initial predictions"""
        self.random_forest_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )

    def _create_neural_model(self):
        """Create neural network model for complex pattern recognition"""
        model = Sequential([
            Dense(128, activation='relu', input_shape=(None,)),
            BatchNormalization(),
            Dropout(0.3),
            Dense(64, activation='relu'),
            BatchNormalization(),
            Dropout(0.2),
            Dense(32, activation='relu'),
            Dense(1, activation='sigmoid')
        ])

        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
        )

        self.neural_model = model

    def _fetch_training_data(self) -> pd.DataFrame:
        """Fetch historical booking data from SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            SELECT
                c.client_id,
                c.age as client_age,
                c.membership_tier,
                c.total_points_balance,
                c.days_since_last_booking,
                c.avg_nights_per_booking,
                c.total_bookings,
                c.preferred_destination_region,
                c.preferred_award_type,
                c.travel_frequency,
                b.award_id,
                b.redemption_success,
                a.award_type,
                a.point_cost,
                a.destination,
                a.region,
                a.partner_airline,
                a.seasonality_score,
                a.availability_score
            FROM clients c
            JOIN bookings b ON c.client_id = b.client_id
            JOIN awards a ON b.award_id = a.award_id
            WHERE b.redemption_success IS NOT NULL
            AND c.total_points_balance > 0
            """

            df = pd.read_sql(query, conn)
            conn.close()

            # Convert boolean redemption_success to binary
            df['redemption_success'] = df['redemption_success'].astype(int)

            logger.info(f"Fetched {len(df)} training records from database")
            return df

        except Exception as e:
            logger.error(f"Error fetching training data: {e}")
            raise

    def _preprocess_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess training data"""
        try:
            # Drop non-feature columns
            feature_cols = ['client_age', 'total_points_balance', 'days_since_last_booking',
                          'avg_nights_per_booking', 'total_bookings', 'membership_tier',
                          'preferred_destination_region', 'preferred_award_type',
                          'travel_frequency', 'point_cost', 'seasonality_score',
                          'availability_score']

            X = df[feature_cols]
            y = df['redemption_success'].values

            # Fit and transform features
            X_processed = self.feature_processor.fit_transform(X)

            # Save scaler and encoder for later use
            joblib.dump(self.feature_processor.named_transformers_['num'], self.models_dir / "scaler.pkl")
            joblib.dump(self.feature_processor.named_transformers_['cat'], self.models_dir / "encoder.pkl")

            logger.info(f"Processed data shape: {X_processed.shape}")
            return X_processed, y

        except Exception as e:
            logger.error(f"Error preprocessing data: {e}")
            raise

    def train_models(self, test_size: float = 0.2, random_state: int = 42):
        """Train both Random Forest and Neural Network models"""
        try:
            logger.info("Starting model training process")

            # Fetch and preprocess data
            df = self._fetch_training_data()
            X, y = self._preprocess_data(df)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=y
            )

            # Train Random Forest
            logger.info("Training Random Forest model...")
            self.random_forest_model.fit(X_train, y_train)
            rf_pred = self.random_forest_model.predict(X_test)
            logger.info(f"Random Forest Accuracy: {accuracy_score(y_test, rf_pred):.4f}")
            logger.info(f"Random Forest Classification Report:\n{classification_report(y_test, rf_pred)}")

            # Save Random Forest model
            joblib.dump(self.random_forest_model, self.models_dir / "random_forest_model.pkl")

            # Train Neural Network
            logger.info("Training Neural Network model...")
            early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
            checkpoint = ModelCheckpoint(
                self.models_dir / "neural_model.h5",
                monitor='val_auc',
                save_best_only=True,
                mode='max'
            )

            history = self.neural_model.fit(
                X_train, y_train,
                validation_data=(X_test, y_test),
                epochs=100,
                batch_size=64,
                callbacks=[early_stopping, checkpoint],
                verbose=1
            )

            # Evaluate Neural Network
            nn_pred = (self.neural_model.predict(X_test) > 0.5).astype(int)
            logger.info(f"Neural Network Accuracy: {accuracy_score(y_test, nn_pred):.4f}")
            logger.info(f"Neural Network Classification Report:\n{classification_report(y_test, nn_pred)}")

            logger.info("Model training completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during model training: {e}")
            raise

    def predict_recommendations(self, client_data: Dict, top_n: int = 5) -> List[Dict]:
        """
        Predict top award recommendations for a client
        Args:
            client_data: Dictionary containing client features
            top_n: Number of recommendations to return
        Returns:
            List of recommended awards with confidence scores
        """
        try:
            # Convert client data to DataFrame
            client_df = pd.DataFrame([client_data])

            # Preprocess client data
            feature_cols = ['client_age', 'total_points_balance', 'days_since_last_booking',
                          'avg_nights_per_booking', 'total_bookings', 'membership_tier',
                          'preferred_destination_region', 'preferred_award_type',
                          'travel_frequency', 'point_cost', 'seasonality_score',
                          'availability_score']

            X_client = client_df[feature_cols]
            X_client_processed = self.feature_processor.transform(X_client)

            # Get predictions from both models
            rf_proba = self.random_forest_model.predict_proba(X_client_processed)[:, 1]
            nn_proba = self.neural_model.predict(X_client_processed).flatten()

            # Combine predictions (simple average)
            combined_proba = (rf_proba + nn_proba) / 2

            # Create recommendations with confidence scores
            recommendations = []
            for i, award_id in enumerate(client_df['award_id']):
                recommendations.append({
                    'award_id': award_id,
                    'confidence_score': float(combined_proba[i]),
                    'model': 'hybrid',
                    'timestamp': datetime.utcnow().isoformat()
                })

            # Sort by confidence score and return top N
            recommendations.sort(key=lambda x: x['confidence_score'], reverse=True)
            return recommendations[:top_n]

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            raise

    def get_award_details(self, award_id: str) -> Optional[Dict]:
        """Get detailed information about a specific award"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            SELECT award_id, award_type, destination, region, partner_airline,
                   point_cost, seasonality_score, availability_score,
                   description, min_nights, max_nights
            FROM awards
            WHERE award_id = ?
            """

            award = conn.execute(query, (award_id,)).fetchone()
            conn.close()

            if award:
                return {
                    'award_id': award[0],
                    'award_type': award[1],
                    'destination': award[2],
                    'region': award[3],
                    'partner_airline': award[4],
                    'point_cost': award[5],
                    'seasonality_score': award[6],
                    'availability_score': award[7],
                    'description': award[8],
                    'min_nights': award[9],
                    'max_nights': award[10]
                }
            return None

        except Exception as e:
            logger.error(f"Error fetching award details: {e}")
            raise

    def update_client_profile(self, client_id: str, booking_data: Dict):
        """Update client profile based on booking behavior"""
        try:
            conn = sqlite3.connect(self.db_path)

            # Update client statistics
            update_query = """
            UPDATE clients
            SET
                total_points_balance = ?,
                days_since_last_booking = 0,
                avg_nights_per_booking = CASE
                    WHEN total_bookings = 0 THEN ?
                    ELSE ((avg_nights_per_booking * total_bookings) + ?) / (total_bookings + 1)
                END,
                total_bookings = total_bookings + 1,
                preferred_destination_region = CASE
                    WHEN ? THEN preferred_destination_region
                    ELSE ?
                END,
                preferred_award_type = CASE
                    WHEN ? THEN preferred_award_type
                    ELSE ?
                END
            WHERE client_id = ?
            """

            conn.execute(update_query, (
                booking_data['points_balance'],
                booking_data['nights'],
                booking_data['nights'],
                booking_data['destination_region'] == 'preferred',
                booking_data['destination_region'],
                booking_data['award_type'] == 'preferred',
                booking_data['award_type'],
                client_id
            ))

            # Record booking
            insert_query = """
            INSERT INTO bookings
            (client_id, award_id, booking_date, nights, points_used, redemption_success)
            VALUES (?, ?, ?, ?, ?, ?)
            """

            conn.execute(insert_query, (
                client_id,
                booking_data['award_id'],
                datetime.utcnow().isoformat(),
                booking_data['nights'],
                booking_data['points_used'],
                booking_data['success']
            ))

            conn.commit()
            conn.close()
            logger.info(f"Updated client profile for {client_id}")

        except Exception as e:
            logger.error(f"Error updating client profile: {e}")
            raise

# Singleton instance for the recommendation engine
recommendation_engine = AwardRecommendationEngine()

if __name__ == "__main__":
    # Example usage
    engine = AwardRecommendationEngine()

    # Train models (in production, this would be scheduled)
    engine.train_models()

    # Example client data
    client_data = {
        'client_id': 'CLIENT-001',
        'client_age': 35,
        'total_points_balance': 150000,
        'days_since_last_booking': 90,
        'avg_nights_per_booking': 7,
        'total_bookings': 12,
        'membership_tier': 'gold',
        'preferred_destination_region': 'europe',
        'preferred_award_type': 'flight',
        'travel_frequency': 'quarterly',
        'award_id': 'AWARD-001',
        'point_cost': 85000,
        'seasonality_score': 0.85,
        'availability_score': 0.92
    }

    # Get recommendations
    recommendations = engine.predict_recommendations(client_data, top_n=5)
    print("Top Recommendations:")
    for rec in recommendations:
        award_details = engine.get_award_details(rec['award_id'])
        print(f"\nAward: {award_details['destination']} ({award_details['award_type']})")
        print(f"Confidence: {rec['confidence_score']:.2%}")
        print(f"Points needed: {award_details['point_cost']}")
        print(f"Region: {award_details['region']}")
