"""
Award Flight Recommender Model
Distributed TensorFlow/Keras model for predicting optimal award flight redemptions
"""

import os
import json
import logging
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.layers import Input, Dense, Concatenate, Embedding, Flatten, BatchNormalization, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, TensorBoard
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
import mlflow
import psycopg2
from datetime import datetime
import hashlib
import warnings

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AwardFlightRecommender:
    """
    AI-powered award flight recommendation system using deep learning
    """

    def __init__(self, config_path='config/model_config.json'):
        """
        Initialize the recommender with configuration
        """
        self.config = self._load_config(config_path)
        self.model = None
        self.preprocessor = None
        self.scaler = None
        self.encoder = None
        self.feature_columns = None
        self.target_column = 'award_miles'
        self.model_version = f"v{datetime.now().strftime('%Y%m%d')}"
        self.model_path = os.path.join('models', f'award_flight_recommender_{self.model_version}')
        self.metrics = {}

        # Initialize MLflow
        self._init_mlflow()

        # Create model directory
        os.makedirs(self.model_path, exist_ok=True)

    def _load_config(self, config_path):
        """Load model configuration"""
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            # Use default config
            return {
                "model": {
                    "hidden_layers": [128, 64, 32],
                    "dropout_rate": 0.2,
                    "learning_rate": 0.001,
                    "batch_size": 256,
                    "epochs": 100,
                    "validation_split": 0.2,
                    "early_stopping_patience": 10
                },
                "features": {
                    "numerical": ['departure_time', 'arrival_time', 'flight_duration', 'distance_km',
                                 'client_age', 'client_income', 'prior_award_redemptions'],
                    "categorical": ['origin_airport', 'destination_airport', 'airline',
                                   'cabin_class', 'client_tier', 'travel_purpose'],
                    "embedding": ['origin_airport', 'destination_airport', 'airline']
                },
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "dbname": "district_award_travel",
                    "user": "ml_user",
                    "password": "secure_password"
                }
            }

    def _init_mlflow(self):
        """Initialize MLflow tracking"""
        try:
            mlflow.set_experiment("award_flight_recommender")
            mlflow.tensorflow.autolog()
            logger.info("MLflow initialized successfully")
        except Exception as e:
            logger.warning(f"MLflow initialization failed: {e}")

    def _connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            conn = psycopg2.connect(
                host=self.config['database']['host'],
                port=self.config['database']['port'],
                dbname=self.config['database']['dbname'],
                user=self.config['database']['user'],
                password=self.config['database']['password']
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def _fetch_training_data(self, limit=None):
        """
        Fetch training data from database
        Returns DataFrame with features and target
        """
        query = """
        SELECT
            f.flight_id,
            f.origin_airport,
            f.destination_airport,
            f.airline,
            f.departure_time,
            f.arrival_time,
            f.flight_duration,
            f.distance_km,
            f.cabin_class,
            c.client_id,
            c.client_age,
            c.client_income,
            c.client_tier,
            c.prior_award_redemptions,
            c.travel_purpose,
            f.award_miles,
            f.seats_available,
            f.partner_airline,
            f.routing_type
        FROM flight_redemptions f
        JOIN clients c ON f.client_id = c.client_id
        WHERE f.seats_available > 0
        ORDER BY f.flight_id
        """

        if limit:
            query += f" LIMIT {limit}"

        try:
            conn = self._connect_db()
            df = pd.read_sql(query, conn)
            conn.close()
            logger.info(f"Fetched {len(df)} training records")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch training data: {e}")
            raise

    def _preprocess_data(self, df):
        """
        Preprocess raw data into features and target
        """
        # Feature engineering
        df['departure_time'] = pd.to_datetime(df['departure_time']).dt.hour
        df['arrival_time'] = pd.to_datetime(df['arrival_time']).dt.hour
        df['flight_duration'] = df['flight_duration'].dt.total_seconds() / 3600
        df['distance_km'] = df['distance_km'] / 1000  # Convert to km

        # Target variable - award miles required
        df['award_miles'] = df['award_miles'].astype(float)

        # Filter out outliers
        q_low = df['award_miles'].quantile(0.01)
        q_hi = df['award_miles'].quantile(0.99)
        df = df[(df['award_miles'] >= q_low) & (df['award_miles'] <= q_hi)]

        # Define features and target
        numerical_features = self.config['features']['numerical']
        categorical_features = self.config['features']['categorical']

        # Separate features and target
        X = df[numerical_features + categorical_features]
        y = df[self.target_column].values

        # Create preprocessing pipeline
        numerical_transformer = Pipeline(steps=[
            ('scaler', StandardScaler())
        ])

        categorical_transformer = Pipeline(steps=[
            ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
        ])

        self.preprocessor = ColumnTransformer(
            transformers=[
                ('num', numerical_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])

        # Fit and transform
        X_processed = self.preprocessor.fit_transform(X)

        # Get feature names after one-hot encoding
        feature_names = numerical_features.copy()
        ohe_feature_names = self.preprocessor.named_transformers_['cat'].named_steps['onehot'].get_feature_names_out(categorical_features)
        feature_names.extend(ohe_feature_names)

        return X_processed, y, feature_names

    def _build_model(self, input_shape):
        """
        Build deep learning model architecture
        """
        # Input layer
        inputs = Input(shape=(input_shape,))

        # Embedding layers for categorical features
        x = Dense(256, activation='relu')(inputs)
        x = BatchNormalization()(x)
        x = Dropout(self.config['model']['dropout_rate'])(x)

        # Hidden layers
        for units in self.config['model']['hidden_layers']:
            x = Dense(units, activation='relu')(x)
            x = BatchNormalization()(x)
            x = Dropout(self.config['model']['dropout_rate'])(x)

        # Output layer - predicting award miles
        outputs = Dense(1, activation='linear')(x)

        # Create model
        model = Model(inputs=inputs, outputs=outputs)

        # Compile model
        optimizer = Adam(learning_rate=self.config['model']['learning_rate'])
        model.compile(
            optimizer=optimizer,
            loss='huber_loss',  # Robust to outliers
            metrics=['mae', 'mse']
        )

        logger.info(f"Model built with {model.count_params()} parameters")
        return model

    def train(self, data_limit=None, test_size=0.2):
        """
        Train the recommendation model
        """
        logger.info("Starting model training...")

        # Fetch and preprocess data
        df = self._fetch_training_data(limit=data_limit)
        X, y, feature_names = self._preprocess_data(df)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # Build model
        self.model = self._build_model(X_train.shape[1])

        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=self.config['model']['early_stopping_patience'],
                restore_best_weights=True
            ),
            ModelCheckpoint(
                filepath=os.path.join(self.model_path, 'best_model.h5'),
                monitor='val_loss',
                save_best_only=True,
                save_weights_only=False
            ),
            TensorBoard(
                log_dir=os.path.join('logs', f'tensorboard_{self.model_version}'),
                histogram_freq=1
            )
        ]

        # Train model
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=self.config['model']['epochs'],
            batch_size=self.config['model']['batch_size'],
            callbacks=callbacks,
            verbose=1
        )

        # Evaluate model
        self._evaluate_model(X_test, y_test, history)

        # Save model and artifacts
        self._save_model_artifacts(X_train, feature_names)

        logger.info("Model training completed successfully")
        return history

    def _evaluate_model(self, X_test, y_test, history):
        """
        Evaluate model performance and log metrics
        """
        # Predictions
        y_pred = self.model.predict(X_test).flatten()

        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mse)

        # Log metrics
        self.metrics = {
            'mse': mse,
            'mae': mae,
            'rmse': rmse,
            'val_loss': min(history.history['val_loss']),
            'training_time': len(history.history['loss'])
        }

        logger.info(f"Model Evaluation Metrics:")
        logger.info(f"  MSE: {mse:.2f}")
        logger.info(f"  MAE: {mae:.2f}")
        logger.info(f"  RMSE: {rmse:.2f}")

        # Log to MLflow
        with mlflow.start_run():
            mlflow.log_metrics(self.metrics)
            mlflow.log_param("model_version", self.model_version)
            mlflow.log_param("training_samples", len(X_test))
            mlflow.set_tag("model_type", "award_flight_recommender")

    def _save_model_artifacts(self, X_train_sample, feature_names):
        """
        Save model and preprocessing artifacts
        """
        # Save model
        model_path = os.path.join(self.model_path, 'model.h5')
        self.model.save(model_path)

        # Save preprocessing artifacts
        artifacts = {
            'preprocessor': self.preprocessor,
            'feature_names': feature_names,
            'model_version': self.model_version,
            'training_timestamp': datetime.now().isoformat(),
            'config': self.config
        }

        # Save scaler separately for numerical features
        numerical_features = self.config['features']['numerical']
        numerical_indices = [i for i, name in enumerate(feature_names) if name in numerical_features]

        if numerical_indices:
            numerical_scaler = StandardScaler()
            numerical_scaler.fit(X_train_sample[:, numerical_indices])
            artifacts['numerical_scaler'] = numerical_scaler

        # Save all artifacts
        joblib.dump(artifacts, os.path.join(self.model_path, 'preprocessor.pkl'))

        logger.info(f"Model and artifacts saved to {self.model_path}")

    def predict(self, client_preferences):
        """
        Predict award miles required for given client preferences
        Returns list of recommended flights with predicted award miles
        """
        if self.model is None or self.preprocessor is None:
            raise ValueError("Model not trained. Call train() first.")

        # Preprocess input
        input_df = pd.DataFrame([client_preferences])

        # Ensure all required features are present
        required_features = self.config['features']['numerical'] + self.config['features']['categorical']
        for feature in required_features:
            if feature not in input_df.columns:
                input_df[feature] = 0  # Default value

        # Preprocess
        X_processed = self.preprocessor.transform(input_df)

        # Predict
        predictions = self.model.predict(X_processed).flatten()

        # Format results
        results = []
        for i, pred in enumerate(predictions):
            results.append({
                'predicted_award_miles': float(pred),
                'confidence': 0.95,  # Placeholder for model confidence
                'model_version': self.model_version,
                'prediction_timestamp': datetime.now().isoformat()
            })

        return results

    def recommend_flights(self, client_id, max_results=10):
        """
        Recommend flights for a specific client based on their profile
        """
        try:
            # Fetch client data
            conn = self._connect_db()
            client_query = "SELECT * FROM clients WHERE client_id = %s"
            client_data = pd.read_sql(client_query, conn, params=(client_id,))
            conn.close()

            if client_data.empty:
                raise ValueError(f"Client {client_id} not found")

            # Get client preferences from their profile
            client_prefs = {
                'client_id': client_id,
                'client_age': client_data['client_age'].iloc[0],
                'client_income': client_data['client_income'].iloc[0],
                'client_tier': client_data['client_tier'].iloc[0],
                'prior_award_redemptions': client_data['prior_award_redemptions'].iloc[0],
                'travel_purpose': client_data['travel_purpose'].iloc[0]
            }

            # Fetch available flights
            flight_query = """
            SELECT
                flight_id, origin_airport, destination_airport, airline,
                departure_time, arrival_time, flight_duration, distance_km,
                cabin_class, award_miles, seats_available, partner_airline,
                routing_type
            FROM flight_redemptions
            WHERE seats_available > 0
            ORDER BY award_miles ASC
            LIMIT 100
            """

            conn = self._connect_db()
            flights_df = pd.read_sql(flight_query, conn)
            conn.close()

            # Generate predictions for each flight
            recommendations = []
            for _, flight in flights_df.iterrows():
                flight_prefs = client_prefs.copy()
                flight_prefs.update({
                    'origin_airport': flight['origin_airport'],
                    'destination_airport': flight['destination_airport'],
                    'airline': flight['airline'],
                    'cabin_class': flight['cabin_class'],
                    'departure_time': pd.to_datetime(flight['departure_time']).hour,
                    'arrival_time': pd.to_datetime(flight['arrival_time']).hour,
                    'flight_duration': flight['flight_duration'].total_seconds() / 3600,
                    'distance_km': flight['distance_km'] / 1000
                })

                prediction = self.predict(flight_prefs)[0]
                flight_dict = flight.to_dict()
                flight_dict.update(prediction)

                recommendations.append(flight_dict)

            # Sort by predicted award miles (lowest first)
            recommendations.sort(key=lambda x: x['predicted_award_miles'])

            return recommendations[:max_results]

        except Exception as e:
            logger.error(f"Failed to recommend flights: {e}")
            raise

    def get_model_info(self):
        """Get model metadata and performance metrics"""
        return {
            'model_version': self.model_version,
            'metrics': self.metrics,
            'config': self.config,
            'last_trained': datetime.now().isoformat()
        }

    def export_model_for_inference(self):
        """
        Export model in a format suitable for inference service
        """
        # Create inference-ready model
        inference_model = tf.keras.models.load_model(
            os.path.join(self.model_path, 'best_model.h5')
        )

        # Save in SavedModel format
        export_path = os.path.join('models', 'inference', f'award_flight_recommender_{self.model_version}')
        inference_model.save(export_path)

        logger.info(f"Model exported for inference to {export_path}")
        return export_path

# CLI interface for training and prediction
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Award Flight Recommender')
    parser.add_argument('--train', action='store_true', help='Train the model')
    parser.add_argument('--predict', action='store_true', help='Make predictions')
    parser.add_argument('--client-id', type=str, help='Client ID for recommendations')
    parser.add_argument('--data-limit', type=int, default=None, help='Limit training data size')

    args = parser.parse_args()

    recommender = AwardFlightRecommender()

    if args.train:
        print("Training model...")
        recommender.train(data_limit=args.data_limit)
        print("Training completed!")

    if args.predict:
        if not args.client_id:
            print("Error: --client-id required for predictions")
            exit(1)

        print(f"Generating recommendations for client {args.client_id}...")
        recommendations = recommender.recommend_flights(args.client_id)
        print(json.dumps(recommendations, indent=2))

    if not (args.train or args.predict):
        print("Use --train to train the model or --predict with --client-id to get recommendations")
