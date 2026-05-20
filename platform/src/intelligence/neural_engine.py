"""
Neural Engine for Award Travel Assistant using NVIDIA NeMo
Handles multimodal input processing, itinerary generation, and trade-off analysis
"""
import os
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from pathlib import Path

import nemo
from nemo.collections.nlp.models import PunctuationCapitalizationModel
from nemo.collections.asr.models import ASRModel
from nemo.collections.nlp.models.language_modeling.megatron_gpt_model import MegatronGPTModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TravelPreferences:
    destination: Optional[str] = None
    travel_class: Optional[str] = None
    max_points: Optional[int] = None
    travel_date: Optional[datetime] = None
    duration: Optional[int] = None
    budget: Optional[float] = None
    flexible_dates: bool = False
    preferred_airlines: Optional[List[str]] = None
    cabin_preferences: Optional[List[str]] = None

@dataclass
class FlightOption:
    airline: str
    flight_number: str
    departure: str
    arrival: str
    departure_time: datetime
    arrival_time: datetime
    duration: timedelta
    points_required: int
    cash_price: float
    cabin_class: str
    layovers: int
    booking_link: str
    score: float

@dataclass
class Itinerary:
    id: str
    title: str
    description: str
    flights: List[FlightOption]
    total_points: int
    total_cash: float
    total_duration: timedelta
    best_option_index: int
    trade_off_explanation: str
    created_at: datetime
    updated_at: datetime

class AwardTravelNeuralEngine:
    """
    Core neural engine for award travel planning with multimodal capabilities
    """

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path or "configs/neural_engine.json")
        self._initialize_models()
        self._initialize_vector_db()
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.preferences_cache = {}

        logger.info("Neural Engine initialized successfully")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load config from {config_path}: {e}")
            return {
                "model_paths": {
                    "punc_cap": "nemo_punctuation_capitalization",
                    "asr": "nemo_asr_en_conformer_ctc",
                    "llm": "nemo_megatron_gpt",
                    "embedding": "sentence-transformers/all-MiniLM-L6-v2"
                },
                "vector_db_path": "data/vector_db.json",
                "cache_size": 1000,
                "similarity_threshold": 0.85
            }

    def _initialize_models(self):
        """Initialize all neural models"""
        try:
            # Punctuation and capitalization model
            self.punc_cap_model = PunctuationCapitalizationModel.from_pretrained(
                self.config["model_paths"]["punc_cap"]
            )

            # ASR model for voice input
            self.asr_model = ASRModel.from_pretrained(
                self.config["model_paths"]["asr"]
            )
            self.asr_model.change_to_deployment_config()

            # LLM for itinerary generation
            self.llm_tokenizer = AutoTokenizer.from_pretrained(
                self.config["model_paths"]["llm"]
            )
            self.llm_model = MegatronGPTModel.from_pretrained(
                self.config["model_paths"]["llm"]
            )

            logger.info("All models initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            raise

    def _initialize_vector_db(self):
        """Initialize vector database for award availability"""
        self.vector_db_path = Path(self.config["vector_db_path"])
        if not self.vector_db_path.exists():
            self.vector_db_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_vector_db([])

        self.vector_db = self._load_vector_db()

    def _load_vector_db(self) -> List[Dict]:
        """Load vector database from file"""
        try:
            with open(self.vector_db_path, 'r') as f:
                return json.load(f)
        except:
            return []

    def _save_vector_db(self, data: List[Dict]):
        """Save vector database to file"""
        with open(self.vector_db_path, 'w') as f:
            json.dump(data, f, indent=2)

    def process_voice_input(self, audio_data: bytes) -> str:
        """
        Process voice input and convert to text
        Args:
            audio_data: Raw audio bytes
        Returns:
            Transcribed text
        """
        try:
            # Save audio to temporary file
            temp_path = Path("temp/audio.wav")
            temp_path.parent.mkdir(exist_ok=True)
            with open(temp_path, 'wb') as f:
                f.write(audio_data)

            # Transcribe using ASR
            transcription = self.asr_model.transcribe([str(temp_path)])[0]

            # Clean up
            temp_path.unlink(missing_ok=True)

            return transcription
        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            return ""

    def process_text_input(self, text: str) -> TravelPreferences:
        """
        Extract travel preferences from natural language text
        Args:
            text: User's natural language input
        Returns:
            Structured travel preferences
        """
        try:
            # Clean and normalize text
            cleaned_text = self._clean_text(text)

            # Use LLM to extract structured information
            prompt = f"""
            Extract travel preferences from the following text. Return JSON format with these fields:
            {{
                "destination": string or null,
                "travel_class": string or null,
                "max_points": integer or null,
                "travel_date": string in YYYY-MM-DD format or null,
                "duration": integer in days or null,
                "budget": float or null,
                "flexible_dates": boolean,
                "preferred_airlines": array of strings or null,
                "cabin_preferences": array of strings or null
            }}

            Text: {cleaned_text}

            JSON:
            """

            inputs = self.llm_tokenizer(prompt, return_tensors="pt")
            outputs = self.llm_model.generate(**inputs, max_length=512)
            result_text = self.llm_tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Parse JSON output
            import json
            try:
                preferences = json.loads(result_text.strip())
            except:
                # Fallback to simple extraction
                preferences = self._fallback_extraction(cleaned_text)

            # Convert to TravelPreferences object
            return TravelPreferences(
                destination=preferences.get("destination"),
                travel_class=preferences.get("travel_class"),
                max_points=preferences.get("max_points"),
                travel_date=self._parse_date(preferences.get("travel_date")),
                duration=preferences.get("duration"),
                budget=preferences.get("budget"),
                flexible_dates=preferences.get("flexible_dates", False),
                preferred_airlines=preferences.get("preferred_airlines"),
                cabin_preferences=preferences.get("cabin_preferences")
            )
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            return TravelPreferences()

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text input"""
        # Apply punctuation and capitalization
        result = self.punc_cap_model.add_punctuation_capitalization([text])[0]
        return result.strip()

    def _fallback_extraction(self, text: str) -> Dict:
        """Fallback extraction method if LLM fails"""
        preferences = {
            "destination": None,
            "travel_class": None,
            "max_points": None,
            "travel_date": None,
            "duration": None,
            "budget": None,
            "flexible_dates": False,
            "preferred_airlines": None,
            "cabin_preferences": None
        }

        # Simple keyword matching
        text_lower = text.lower()

        # Extract destination
        destinations = ["japan", "europe", "asia", "australia", "africa", "south america"]
        for dest in destinations:
            if dest in text_lower:
                preferences["destination"] = dest.capitalize()
                break

        # Extract travel class
        classes = ["economy", "premium economy", "business", "first"]
        for cls in classes:
            if cls in text_lower:
                preferences["travel_class"] = cls
                break

        # Extract points
        import re
        points_match = re.search(r'(\d+)\s*(?:points?|miles?)', text_lower)
        if points_match:
            preferences["max_points"] = int(points_match.group(1))

        # Extract dates
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text_lower)
        if date_match:
            preferences["travel_date"] = date_match.group(1)

        return preferences

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime object"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return None

    def search_award_availability(self, preferences: TravelPreferences) -> List[FlightOption]:
        """
        Search for award flight availability based on preferences
        Args:
            preferences: TravelPreferences object
        Returns:
            List of available flight options
        """
        # In a real implementation, this would query airline APIs and award databases
        # For now, return mock data based on preferences

        mock_flights = []

        if preferences.destination:
            destinations = [preferences.destination.lower()]
        else:
            destinations = ["japan", "europe", "asia", "australia"]

        if preferences.travel_class:
            classes = [preferences.travel_class.lower()]
        else:
            classes = ["business", "first", "premium economy", "economy"]

        base_date = preferences.travel_date or datetime.now()

        for dest in destinations:
            for cls in classes:
                for i in range(3):  # Generate 3 mock options per combination
                    flight = FlightOption(
                        airline="ANA" if "japan" in dest else "United",
                        flight_number=f"{'NH' if 'japan' in dest else 'UA'}9{87 + i}",
                        departure="LAX" if "japan" in dest else "SFO",
                        arrival="HND" if "japan" in dest else "LHR",
                        departure_time=base_date + timedelta(days=i, hours=8 + i*2),
                        arrival_time=base_date + timedelta(days=i, hours=18 + i*2),
                        duration=timedelta(hours=12 + i*2),
                        points_required=min(80000, 50000 + i*10000),
                        cash_price=1200.0 + i*200,
                        cabin_class=cls,
                        layovers=i,
                        booking_link=f"https://awardtravel.example.com/book/{i}",
                        score=0.85 - i*0.05
                    )
                    mock_flights.append(flight)

        # Filter by max points if specified
        if preferences.max_points:
            mock_flights = [f for f in mock_flights if f.points_required <= preferences.max_points]

        return mock_flights

    def generate_itineraries(self, preferences: TravelPreferences) -> List[Itinerary]:
        """
        Generate multiple itinerary options based on preferences
        Args:
            preferences: TravelPreferences object
        Returns:
            List of optimized itineraries
        """
        # Search for available flights
        flight_options = self.search_award_availability(preferences)

        if not flight_options:
            return []

        # Group flights by similar routes
        itineraries = self._group_into_itineraries(flight_options)

        # Score and rank itineraries
        for itinerary in itineraries:
            itinerary.score_itinerary()

        # Sort by score (descending)
        itineraries.sort(key=lambda x: x.score, reverse=True)

        return itineraries[:5]  # Return top 5

    def _group_into_itineraries(self, flights: List[FlightOption]) -> List[Itinerary]:
        """Group flights into complete itineraries"""
        itineraries = []

        # Simple grouping by destination and date
        # In production, this would be more sophisticated
        for i, flight in enumerate(flights):
            itinerary = Itinerary(
                id=f"itinerary_{i}",
                title=f"Trip to {flight.arrival} on {flight.departure_time.strftime('%Y-%m-%d')}",
                description=f"Round trip to {flight.arrival} in {flight.cabin_class} class",
                flights=[flight],
                total_points=flight.points_required,
                total_cash=flight.cash_price,
                total_duration=flight.duration,
                best_option_index=0,
                trade_off_explanation="Direct flight with no layovers",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            itineraries.append(itinerary)

        return itineraries

    def explain_tradeoffs(self, itineraries: List[Itinerary]) -> str:
        """
        Generate explanation of trade-offs between itinerary options
        Args:
            itineraries: List of itineraries
        Returns:
            Explanation string
        """
        if not itineraries:
            return "No itineraries available to compare."

        # Calculate metrics
        points_range = f"{min(i.total_points for i in itineraries)} - {max(i.total_points for i in itineraries)} points"
        cash_range = f"${min(i.total_cash for i in itineraries):.2f} - ${max(i.total_cash for i in itineraries):.2f}"
        duration_range = f"{min(i.total_duration.total_seconds()/3600 for i in itineraries):.1f} - {max(i.total_duration.total_seconds()/3600 for i in itineraries):.1f} hours"

        explanation = f"""
        Here are the trade-offs between your options:

        1. Points vs. Cash: You can choose between {points_range} and spend between {cash_range}
        2. Travel Time: Options range from {duration_range}
        3. Convenience: Direct flights save time but may cost more points
        4. Flexibility: Some options allow date changes for a fee

        Recommendation: The best option balances your points budget with travel time.
        """

        return explanation.strip()

    def vector_search_awards(self, query: str, k: int = 5) -> List[Dict]:
        """
        Vector search for award availability
        Args:
            query: Search query
            k: Number of results to return
        Returns:
            List of matching award options
        """
        query_embedding = self.similarity_model.encode(query)

        # Calculate similarities
        similarities = []
        for item in self.vector_db:
            item_embedding = np.array(item['embedding'])
            similarity = cosine_similarity(
                [query_embedding],
                [item_embedding]
            )[0][0]
            similarities.append((similarity, item))

        # Sort by similarity
        similarities.sort(reverse=True, key=lambda x: x[0])

        return [item for (score, item) in similarities[:k]]

    def add_to_vector_db(self, data: Dict):
        """Add new award data to vector database"""
        embedding = self.similarity_model.encode(data['text'])
        data['embedding'] = embedding.tolist()

        self.vector_db.append(data)
        self._save_vector_db(self.vector_db)

    def cache_preferences(self, user_id: str, preferences: TravelPreferences):
        """Cache user preferences"""
        self.preferences_cache[user_id] = preferences

    def get_cached_preferences(self, user_id: str) -> Optional[TravelPreferences]:
        """Retrieve cached preferences"""
        return self.preferences_cache.get(user_id)

# Initialize the neural engine
neural_engine = AwardTravelNeuralEngine()

# Export for use in other modules
__all__ = ['neural_engine', 'TravelPreferences', 'FlightOption', 'Itinerary']
