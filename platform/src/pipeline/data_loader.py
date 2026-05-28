"""
Data Pipeline: Award Travel Data Loader
Handles loading, validating, and preprocessing award travel data
from various sources into a standardized format.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
import sqlite3
from datetime import datetime
import json
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AwardTravelDataLoader:
    """
    Pipeline component for loading and preprocessing award travel data.
    Handles CSV, JSON, and database sources.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.raw_data_dir = self.data_dir / "raw"
        self.processed_data_dir = self.data_dir / "processed"

        # Create directories if they don't exist
        self._ensure_directories()

        # Data schemas
        self.travel_option_schema = {
            'id': str,
            'destination': str,
            'airline': str,
            'departure_city': str,
            'cabin_class': str,
            'points_required': int,
            'estimated_retail_price': float,
            'duration_days': int,
            'season': str,
            'is_special_offer': bool,
            'last_updated': str,
            'metadata': dict
        }

        self.user_preferences_schema = {
            'user_id': str,
            'preferred_destinations': list,
            'preferred_airlines': list,
            'budget': int,
            'travel_style': str,
            'season': str,
            'last_updated': str
        }

        self.user_history_schema = {
            'user_id': str,
            'travel_option_id': str,
            'points_used': int,
            'travel_date': str,
            'rating': float,
            'notes': str
        }

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.data_dir,
            self.raw_data_dir,
            self.processed_data_dir,
            self.data_dir / "cache"
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def load_travel_options_from_csv(self, file_path: str) -> pd.DataFrame:
        """
        Load travel options from CSV file
        """
        try:
            df = pd.read_csv(file_path)

            # Validate and clean data
            df = self._validate_travel_options(df)

            # Save processed data
            output_path = self.processed_data_dir / "travel_options.csv"
            df.to_csv(output_path, index=False)

            logger.info(f"Successfully loaded {len(df)} travel options from {file_path}")
            return df

        except Exception as e:
            logger.error(f"Error loading travel options from CSV: {e}")
            raise

    def load_travel_options_from_json(self, file_path: str) -> pd.DataFrame:
        """
        Load travel options from JSON file
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Validate and clean data
            df = self._validate_travel_options(df)

            # Save processed data
            output_path = self.processed_data_dir / "travel_options.csv"
            df.to_csv(output_path, index=False)

            logger.info(f"Successfully loaded {len(df)} travel options from {file_path}")
            return df

        except Exception as e:
            logger.error(f"Error loading travel options from JSON: {e}")
            raise

    def _validate_travel_options(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and clean travel options data
        """
        try:
            # Ensure required columns exist
            required_columns = ['id', 'destination', 'airline', 'points_required']
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")

            # Clean data
            df = df.copy()

            # Standardize destination names
            df['destination'] = df['destination'].str.strip().str.title()

            # Standardize airline names
            df['airline'] = df['airline'].str.strip().str.upper()

            # Ensure points_required is integer
            df['points_required'] = pd.to_numeric(df['points_required'], errors='coerce').fillna(0).astype(int)

            # Ensure estimated_retail_price is float
            if 'estimated_retail_price' in df.columns:
                df['estimated_retail_price'] = pd.to_numeric(df['estimated_retail_price'], errors='coerce').fillna(0.0)

            # Ensure cabin_class is valid
            valid_cabin_classes = ['economy', 'premium_economy', 'business_class', 'first_class']
            df['cabin_class'] = df['cabin_class'].str.lower().apply(
                lambda x: x if x in valid_cabin_classes else 'economy'
            )

            # Ensure season is valid
            valid_seasons = ['spring', 'summer', 'fall', 'winter', 'any']
            df['season'] = df['season'].str.lower().apply(
                lambda x: x if x in valid_seasons else 'any'
            )

            # Ensure is_special_offer is boolean
            if 'is_special_offer' not in df.columns:
                df['is_special_offer'] = False
            else:
                df['is_special_offer'] = df['is_special_offer'].fillna(False).astype(bool)

            # Set last_updated if not present
            if 'last_updated' not in df.columns:
                df['last_updated'] = datetime.now().strftime('%Y-%m-%d')

            # Ensure metadata is dict
            if 'metadata' not in df.columns:
                df['metadata'] = [{} for _ in range(len(df))]

            # Drop rows with missing required fields
            df = df.dropna(subset=['id', 'destination', 'airline', 'points_required'])

            return df

        except Exception as e:
            logger.error(f"Error validating travel options: {e}")
            raise

    def load_user_preferences(self, file_path: str) -> Dict:
        """
        Load user preferences from JSON file
        """
        try:
            with open(file_path, 'r') as f:
                preferences = json.load(f)

            # Validate preferences
            validated = {}
            for user_id, prefs in preferences.items():
                validated[user_id] = self._validate_user_preferences(prefs)

            # Save processed preferences
            output_path = self.processed_data_dir / "user_preferences.json"
            with open(output_path, 'w') as f:
                json.dump(validated, f, indent=2)

            logger.info(f"Successfully loaded user preferences for {len(validated)} users")
            return validated

        except Exception as e:
            logger.error(f"Error loading user preferences: {e}")
            raise

    def _validate_user_preferences(self, prefs: Dict) -> Dict:
        """
        Validate and clean user preferences
        """
        try:
            validated = {
                'preferred_destinations': [],
                'preferred_airlines': [],
                'budget': 5000,
                'travel_style': 'balanced',
                'season': 'any',
                'last_updated': datetime.now().strftime('%Y-%m-%d')
            }

            # Validate preferred destinations
            if 'preferred_destinations' in prefs:
                validated['preferred_destinations'] = [
                    dest.strip().title() for dest in prefs['preferred_destinations']
                    if isinstance(dest, str) and dest.strip()
                ]

            # Validate preferred airlines
            if 'preferred_airlines' in prefs:
                validated['preferred_airlines'] = [
                    airline.strip().upper() for airline in prefs['preferred_airlines']
                    if isinstance(airline, str) and airline.strip()
                ]

            # Validate budget
            if 'budget' in prefs:
                try:
                    validated['budget'] = int(prefs['budget'])
                except (ValueError, TypeError):
                    validated['budget'] = 5000

            # Validate travel style
            valid_styles = ['luxury', 'adventure', 'family', 'balanced']
            if 'travel_style' in prefs and prefs['travel_style'].lower() in valid_styles:
                validated['travel_style'] = prefs['travel_style'].lower()

            # Validate season
            valid_seasons = ['spring', 'summer', 'fall', 'winter', 'any']
            if 'season' in prefs and prefs['season'].lower() in valid_seasons:
                validated['season'] = prefs['season'].lower()

            return validated

        except Exception as e:
            logger.error(f"Error validating user preferences: {e}")
            return {
                'preferred_destinations': [],
                'preferred_airlines': [],
                'budget': 5000,
                'travel_style': 'balanced',
                'season': 'any',
                'last_updated': datetime.now().strftime('%Y-%m-%d')
            }

    def load_user_history(self, file_path: str) -> pd.DataFrame:
        """
        Load user travel history from CSV file
        """
        try:
            df = pd.read_csv(file_path)

            # Validate and clean data
            df = self._validate_user_history(df)

            # Save processed data
            output_path = self.processed_data_dir / "user_history.csv"
            df.to_csv(output_path, index=False)

            logger.info(f"Successfully loaded user history for {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error loading user history: {e}")
            raise

    def _validate_user_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and clean user history data
        """
        try:
            # Ensure required columns exist
            required_columns = ['user_id', 'travel_option_id', 'points_used']
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")

            # Clean data
            df = df.copy()

            # Ensure user_id is string
            df['user_id'] = df['user_id'].astype(str)

            # Ensure travel_option_id is string
            df['travel_option_id'] = df['travel_option_id'].astype(str)

            # Ensure points_used is integer
            df['points_used'] = pd.to_numeric(df['points_used'], errors='coerce').fillna(0).astype(int)

            # Ensure travel_date is valid date
            if 'travel_date' in df.columns:
                df['travel_date'] = pd.to_datetime(df['travel_date'], errors='coerce').dt.strftime('%Y-%m-%d')
                df = df.dropna(subset=['travel_date'])

            # Ensure rating is valid (0-5)
            if 'rating' in df.columns:
                df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
                df['rating'] = df['rating'].clip(0, 5)

            # Set last_updated if not present
            if 'last_updated' not in df.columns:
                df['last_updated'] = datetime.now().strftime('%Y-%m-%d')

            # Drop rows with missing required fields
            df = df.dropna(subset=['user_id', 'travel_option_id', 'points_used'])

            return df

        except Exception as e:
            logger.error(f"Error validating user history: {e}")
            raise

    def load_all_data(self) -> Dict:
        """
        Load all award travel data from various sources
        """
        result = {
            'travel_options': None,
            'user_preferences': {},
            'user_history': None,
            'status': 'pending',
            'errors': []
        }

        try:
            # Load travel options
            travel_csv = self.raw_data_dir / "travel_options.csv"
            travel_json = self.raw_data_dir / "travel_options.json"

            if travel_csv.exists():
                result['travel_options'] = self.load_travel_options_from_csv(str(travel_csv))
            elif travel_json.exists():
                result['travel_options'] = self.load_travel_options_from_json(str(travel_json))
            else:
                result['errors'].append("No travel options data found in raw directory")

            # Load user preferences
            prefs_file = self.raw_data_dir / "user_preferences.json"
            if prefs_file.exists():
                result['user_preferences'] = self.load_user_preferences(str(prefs_file))

            # Load user history
            history_file = self.raw_data_dir / "user_history.csv"
            if history_file.exists():
                result['user_history'] = self.load_user_history(str(history_file))

            result['status'] = 'success'
            logger.info("Successfully loaded all award travel data")

        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(str(e))
            logger.error(f"Error loading all data: {e}")

        return result

    def export_to_sqlite(self, db_path: str = "data/award_travel.db"):
        """
        Export processed data to SQLite database
        """
        try:
            conn = sqlite3.connect(db_path)

            # Export travel options
            if self.processed_data_dir.joinpath("travel_options.csv").exists():
                travel_df = pd.read_csv(self.processed_data_dir / "travel_options.csv")
                travel_df.to_sql('travel_options', conn, if_exists='replace', index=False)

            # Export user preferences
            if self.processed_data_dir.joinpath("user_preferences.json").exists():
                with open(self.processed_data_dir / "user_preferences.json", 'r') as f:
                    prefs = json.load(f)
                # Convert to DataFrame for SQLite
                prefs_df = pd.DataFrame([
                    {'user_id': uid, **prefs}
                    for uid, prefs in prefs.items()
                ])
                prefs_df.to_sql('user_preferences', conn, if_exists='replace', index=False)

            # Export user history
            if self.processed_data_dir.joinpath("user_history.csv").exists():
                history_df = pd.read_csv(self.processed_data_dir / "user_history.csv")
                history_df.to_sql('user_history', conn, if_exists='replace', index=False)

            conn.close()
            logger.info(f"Successfully exported data to SQLite database: {db_path}")

        except Exception as e:
            logger.error(f"Error exporting to SQLite: {e}")
            raise

# Example usage
if __name__ == "__main__":
    loader = AwardTravelDataLoader()

    # Example: Load sample data
    sample_data = {
        'id': ['TO001', 'TO002', 'TO003'],
        'destination': ['Japan', 'Europe', 'Australia'],
        'airline': ['ANA', 'Lufthansa', 'Qantas'],
        'points_required': [75000, 80000, 90000],
        'cabin_class': ['business_class', 'business_class', 'first_class'],
        'season': ['spring', 'summer', 'winter']
    }

    sample_df = pd.DataFrame(sample_data)
    sample_df.to_csv(loader.raw_data_dir / "travel_options.csv", index=False)

    # Load the data
    result = loader.load_all_data()
    print(f"Loaded data status: {result['status']}")
    if result['travel_options'] is not None:
        print(f"Travel options loaded: {len(result['travel_options'])}")
