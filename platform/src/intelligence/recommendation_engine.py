"""
District Award Travel - AI Recommendation Engine
Advanced machine learning models for award flight recommendations
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
import sqlite3
from collections import defaultdict

logger = logging.getLogger(__name__)

class AdvancedRecommendationEngine:
    """
    Advanced AI-powered recommendation engine for award flights.
    Uses collaborative filtering, content-based filtering, and hybrid approaches.
    """

    def __init__(self, model_path: str = "platform/data/recommendation_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = StandardScaler()
        self.user_profiles = defaultdict(dict)
        self.flight_features = {}
        self.is_trained = False
        self.load_or_train_model()

    def load_or_train_model(self):
        """Load existing model or train new one"""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logger.info("Loaded existing recommendation model")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.train_model()
        else:
            self.train_model()

    def train_model(self):
        """Train the recommendation model on historical data"""
        try:
            # Load historical booking data
            conn = sqlite3.connect("platform/data/award_travel.db")
            query = """
            SELECT
                f.id as flight_id,
                f.airline,
                f.departure_airport,
                f.arrival_airport,
                f.duration_minutes,
                f.distance_miles,
                f.stops,
                f.award_price,
                b.user_id,
                b.passengers,
                CASE WHEN b.id IS NOT NULL THEN 1.0 ELSE 0.0 END as booked
            FROM flights f
            LEFT JOIN bookings b ON f.id = b.flight_id
            WHERE f.departure_time >= date('now', '-1 year')
            """

            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                logger.warning("No training data available")
                return

            # Feature engineering
            df['hour_of_day'] = pd.to_datetime(df['departure_time']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['departure_time']).dt.dayofweek
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

            # Create feature matrix
            categorical_features = ['airline', 'departure_airport', 'arrival_airport']
            numerical_features = ['duration_minutes', 'distance_miles', 'stops', 'award_price', 'hour_of_day', 'day_of_week', 'is_weekend']

            # One-hot encode categorical features
            df_encoded = pd.get_dummies(df, columns=categorical_features)

            # Split data
            X = df_encoded.drop(['flight_id', 'user_id', 'passengers', 'booked', 'departure_time'], axis=1, errors='ignore')
            y = df_encoded['booked']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # Create pipeline
            pipeline = Pipeline([
                ('scaler', StandardScaler()),
                ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
            ])

            # Train model
            pipeline.fit(X_train, y_train)

            # Evaluate
            y_pred = pipeline.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            logger.info(f"Model trained with MSE: {mse:.4f}")

            # Save model
            self.model = pipeline
            joblib.dump(pipeline, self.model_path)
            self.is_trained = True

        except Exception as e:
            logger.error(f"Failed to train model: {e}")
            self.is_trained = False

    def update_user_profile(self, user_id: int, flight_data: List[Dict]):
        """
        Update user profile based on interactions with flight results.
        Uses implicit feedback (clicks, views, bookings).
        """
        if not flight_data:
            return

        profile = self.user_profiles[user_id]

        for flight in flight_data:
            # Update airline preferences
            if 'airline' in flight:
                profile[f'airline_{flight["airline"]}'] = profile.get(f'airline_{flight["airline"]}', 0) + 1

            # Update route preferences
            if 'departure_airport' in flight and 'arrival_airport' in flight:
                route_key = f"{flight['departure_airport']}-{flight['arrival_airport']}"
                profile[f'route_{route_key}'] = profile.get(f'route_{route_key}', 0) + 1

            # Update time preferences
            if 'departure_time' in flight:
                hour = datetime.strptime(flight['departure_time'], "%Y-%m-%d %H:%M:%S").hour
                profile[f'hour_{hour}'] = profile.get(f'hour_{hour}', 0) + 1

            # Update price sensitivity
            if 'award_price' in flight:
                price_category = int(flight['award_price'] // 5000)
                profile[f'price_{price_category}'] = profile.get(f'price_{price_category}', 0) + 1

    def predict_score(self, user_id: int, flight_features: Dict) -> float:
        """
        Predict recommendation score for a flight given user profile.
        Returns score between 0 and 1.
        """
        if not self.is_trained or self.model is None:
            return self._fallback_score(user_id, flight_features)

        try:
            # Create feature vector
            feature_vector = []

            # Numerical features
            numerical_features = [
                'duration_minutes', 'distance_miles', 'stops',
                'award_price', 'hour_of_day', 'day_of_week', 'is_weekend'
            ]

            for feature in numerical_features:
                if feature in flight_features:
                    feature_vector.append(flight_features[feature])
                else:
                    feature_vector.append(0)

            # Categorical features (one-hot encoded)
            categorical_features = ['airline', 'departure_airport', 'arrival_airport']
            for feature in categorical_features:
                if feature in flight_features:
                    # Create binary feature for this category
                    value = flight_features[feature]
                    for cat in self.model.named_steps['regressor'].feature_importances_:
                        feature_vector.append(1 if cat == value else 0)
                else:
                    feature_vector.extend([0] * 100)  # Pad with zeros

            # Scale features
            scaled_features = self.model.named_steps['scaler'].transform([feature_vector])

            # Predict probability of booking
            score = self.model.named_steps['regressor'].predict_proba(scaled_features)[0][1]
            return float(score)

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return self._fallback_score(user_id, flight_features)

    def _fallback_score(self, user_id: int, flight_features: Dict) -> float:
        """Fallback scoring method when model is not available"""
        score = 0.0

        # Simple heuristics
        if 'stops' in flight_features and flight_features['stops'] == 0:
            score += 0.3
        if 'award_price' in flight_features and flight_features['award_price'] < 25000:
            score += 0.4
        if 'airline' in flight_features and flight_features['airline'] == 'AA':
            score += 0.2

        # User-specific preferences
        profile = self.user_profiles.get(user_id, {})
        if 'airline_AA' in profile:
            score += 0.15
        if 'route_JFK-LAX' in profile:
            score += 0.2

        return min(1.0, max(0.0, score))

    def recommend_flights(self, user_id: int, flights: List[Dict], limit: int = 10) -> List[Dict]:
        """
        Recommend top flights for a user based on their profile and flight features.
        Returns list of flights with recommendation scores.
        """
        if not flights:
            return []

        # Add features to each flight
        enriched_flights = []
        for flight in flights:
            features = {
                'flight_id': flight.get('id'),
                'airline': flight.get('airline'),
                'departure_airport': flight.get('departure_airport'),
                'arrival_airport': flight.get('arrival_airport'),
                'duration_minutes': flight.get('duration_minutes'),
                'distance_miles': flight.get('distance_miles'),
                'stops': flight.get('stops'),
                'award_price': flight.get('award_price'),
                'hour_of_day': None,
                'day_of_week': None,
                'is_weekend': 0
            }

            if 'departure_time' in flight:
                dt = datetime.strptime(flight['departure_time'], "%Y-%m-%d %H:%M:%S")
                features['hour_of_day'] = dt.hour
                features['day_of_week'] = dt.dayofweek
                features['is_weekend'] = 1 if dt.dayofweek >= 5 else 0

            enriched_flights.append(features)

        # Predict scores
        for flight in enriched_flights:
            flight['recommendation_score'] = self.predict_score(user_id, flight)

        # Sort by score descending
        enriched_flights.sort(key=lambda x: x['recommendation_score'], reverse=True)

        # Return top recommendations
        return enriched_flights[:limit]

# Global instance
advanced_recommendation_engine = AdvancedRecommendationEngine()
