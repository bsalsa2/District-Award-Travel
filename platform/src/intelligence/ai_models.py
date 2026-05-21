"""
AI Models for District Award Travel Assistant
Includes NLP models, award valuation, and recommendation engines
"""

import numpy as np
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import joblib
import os
from pathlib import Path
from platform.src.database.models import AwardRecommendation
from platform.src.database import get_db
from platform.src.observability.metrics import track_metric

logger = logging.getLogger(__name__)

class AwardValuationEngine:
    """
    AI-powered award valuation engine that calculates the monetary value of award redemptions
    across multiple loyalty programs.
    """

    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.val_models = self._load_valuation_models()
        self.tfidf_vectorizer = TfidfVectorizer(max_features=5000)

    def _load_valuation_models(self) -> Dict[str, Any]:
        """Load pre-trained valuation models for different programs"""
        models = {}

        # Load cached models if available
        cache_path = Path("platform/data/valuation_models")
        cache_path.mkdir(parents=True, exist_ok=True)

        # Example: Load a simple valuation model (in production, these would be trained models)
        models["generic"] = {
            "base_value": 0.01,  # $0.01 per point as default
            "multipliers": {
                "first_class": 3.0,
                "business_class": 2.0,
                "economy": 1.0,
                "partner_transfer": 0.8,
                "sweet_spot": 0.02
            },
            "seasonal_adjustments": {
                "peak": 1.2,
                "off_peak": 0.8
            }
        }

        # Load program-specific models
        program_models = {
            "aa": {"base_value": 0.011, "multiplier": 1.0},
            "dl": {"base_value": 0.012, "multiplier": 1.1},
            "ua": {"base_value": 0.0105, "multiplier": 0.95},
            "ba": {"base_value": 0.0095, "multiplier": 0.9},
            "sq": {"base_value": 0.013, "multiplier": 1.2},
            "hyatt": {"base_value": 0.008, "multiplier": 0.8},
            "ihg": {"base_value": 0.007, "multiplier": 0.7},
            "marriott": {"base_value": 0.0075, "multiplier": 0.75}
        }

        for program, config in program_models.items():
            models[program] = config

        return models

    def calculate_award_value(self, award_data: Dict[str, Any]) -> float:
        """
        Calculate the monetary value of an award redemption

        Args:
            award_data: Dictionary containing award information

        Returns:
            float: Estimated monetary value in USD
        """
        try:
            program = award_data.get("program", "generic").lower()
            points = award_data.get("points", 0)
            cabin = award_data.get("cabin", "economy").lower()
            partner = award_data.get("partner", False)
            season = award_data.get("season", "off_peak")

            # Get program-specific model
            model = self.val_models.get(program, self.val_models["generic"])

            # Calculate base value
            base_value = model["base_value"]
            if partner:
                base_value *= model["multipliers"].get("partner_transfer", 0.8)

            # Apply cabin multiplier
            cabin_multiplier = model["multipliers"].get(cabin, 1.0)
            value = points * base_value * cabin_multiplier

            # Apply seasonal adjustment
            seasonal_adj = model["seasonal_adjustments"].get(season, 1.0)
            value *= seasonal_adj

            # Apply sweet spot multiplier if applicable
            if "sweet_spot" in model["multipliers"]:
                sweet_spot_value = points * model["multipliers"]["sweet_spot"]
                value = max(value, sweet_spot_value)

            track_metric("award_valuation_calculated", {"program": program, "cabin": cabin})
            return round(value, 2)

        except Exception as e:
            logger.error(f"Error calculating award value: {str(e)}")
            track_metric("award_valuation_error", {"error": str(e)})
            return 0.0

    def get_award_comparison(self, awards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compare multiple award options and rank them by value

        Args:
            awards: List of award dictionaries

        Returns:
            List of ranked awards with calculated values
        """
        for award in awards:
            award["calculated_value"] = self.calculate_award_value(award)

        # Sort by value descending
        ranked = sorted(awards, key=lambda x: x["calculated_value"], reverse=True)

        # Add ranking
        for idx, award in enumerate(ranked, 1):
            award["rank"] = idx

        return ranked

class NLPProcessor:
    """
    Natural Language Processing engine for understanding travel queries
    """

    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.intent_model = self._load_intent_model()
        self.entity_extractor = self._load_entity_extractor()

    def _load_intent_model(self) -> Dict[str, Any]:
        """Load intent classification model"""
        return {
            "intents": {
                "search_awards": ["find", "search", "look for", "find me", "show me"],
                "compare_awards": ["compare", "which is better", "vs", "versus"],
                "book_award": ["book", "reserve", "hold", "save"],
                "check_availability": ["available", "availability", "open"],
                "get_help": ["help", "support", "assistance", "advice"],
                "recommend": ["recommend", "suggest", "what should I use"],
                "explain": ["explain", "what is", "how does"]
            },
            "default_intent": "search_awards"
        }

    def _load_entity_extractor(self) -> Dict[str, Any]:
        """Load entity extraction patterns"""
        return {
            "destinations": ["to [destination]", "for [destination]", "in [destination]"],
            "dates": ["on [date]", "for [date]", "between [date] and [date]"],
            "cabin": ["[cabin] class", "in [cabin] class", "upgrade to [cabin]"],
            "program": ["[program] points", "[program] miles", "[program] rewards"],
            "points": ["[points] points", "[points] miles", "[points] k points"]
        }

    def extract_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract intent and entities from a natural language query

        Args:
            query: User's natural language query

        Returns:
            Dictionary containing intent and extracted entities
        """
        query_lower = query.lower()
        intent = self.intent_model["default_intent"]
        entities = {}

        # Check for each intent
        for intent_name, keywords in self.intent_model["intents"].items():
            for keyword in keywords:
                if keyword in query_lower:
                    intent = intent_name
                    break
            if intent != self.intent_model["default_intent"]:
                break

        # Extract entities using simple pattern matching
        if "destination" in query_lower or "to " in query_lower:
            entities["destination"] = self._extract_destination(query)

        if any(word in query_lower for word in ["points", "miles"]):
            entities["points"] = self._extract_points(query)

        if any(word in query_lower for word in ["economy", "business", "first"]):
            entities["cabin"] = self._extract_cabin(query)

        if any(word in query_lower for word in ["aa", "delta", "united", "american"]):
            entities["program"] = self._extract_program(query)

        # Extract dates
        entities["dates"] = self._extract_dates(query)

        track_metric("nlp_intent_extracted", {"intent": intent, "entities": list(entities.keys())})
        return {
            "intent": intent,
            "entities": entities,
            "query": query,
            "processed_at": datetime.utcnow().isoformat()
        }

    def _extract_destination(self, query: str) -> str:
        """Extract destination from query"""
        # Simple extraction - in production use NER
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["to", "for", "in"]:
                if i + 1 < len(words):
                    return words[i + 1]
        return ""

    def _extract_points(self, query: str) -> int:
        """Extract points value from query"""
        import re
        match = re.search(r'(\d+(?:,\d+)*)\s*(?:points|miles|k)', query, re.IGNORECASE)
        if match:
            points_str = match.group(1).replace(",", "")
            try:
                return int(points_str)
            except ValueError:
                pass
        return 0

    def _extract_cabin(self, query: str) -> str:
        """Extract cabin class from query"""
        query_lower = query.lower()
        if "first" in query_lower:
            return "first_class"
        elif "business" in query_lower:
            return "business_class"
        elif "economy" in query_lower:
            return "economy"
        return "economy"

    def _extract_program(self, query: str) -> str:
        """Extract loyalty program from query"""
        query_lower = query.lower()
        programs = {
            "aa": ["american", "aa", "aadvantage"],
            "dl": ["delta", "dl", "skymiles"],
            "ua": ["united", "ua", "miles"],
            "ba": ["british airways", "ba", "avios"],
            "sq": ["singapore", "sq", " KrisFlyer"],
            "hyatt": ["hyatt", "world of hyatt"],
            "ihg": ["ihg", "intercontinental", "holiday inn"],
            "marriott": ["marriott", "bonvoy"]
        }

        for program, keywords in programs.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return program
        return "generic"

    def _extract_dates(self, query: str) -> List[str]:
        """Extract date ranges from query"""
        import re
        from dateparser import parse

        dates = []
        # Simple date pattern matching
        date_patterns = [
            r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b'
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                try:
                    parsed = parse(match)
                    if parsed:
                        dates.append(parsed.isoformat())
                except:
                    pass

        return dates if dates else []

    def generate_response(self, intent_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Generate a natural language response based on intent and context

        Args:
            intent_data: Intent and entities from extract_intent
            context: Additional context from conversation

        Returns:
            Natural language response string
        """
        intent = intent_data["intent"]
        entities = intent_data["entities"]

        responses = {
            "search_awards": self._generate_search_response(entities, context),
            "compare_awards": self._generate_compare_response(entities, context),
            "book_award": self._generate_book_response(entities, context),
            "check_availability": self._generate_availability_response(entities, context),
            "get_help": "I'd be happy to help! What do you need assistance with regarding award travel?",
            "recommend": self._generate_recommend_response(entities, context),
            "explain": self._generate_explain_response(entities, context)
        }

        return responses.get(intent, "I understand your request. Let me look into that for you.")

    def _generate_search_response(self, entities: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for search_awards intent"""
        program = entities.get("program", "programs")
        cabin = entities.get("cabin", "any cabin")
        points = entities.get("points", "some points")

        if points > 0:
            return f"I'll search for award options using {points:,} {program} points in {cabin} class."
        else:
            return f"I'll help you find award travel options. Which {program} are you considering?"

    def _generate_compare_response(self, entities: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for compare_awards intent"""
        return "I'll compare those award options and show you the best value based on your criteria."

    def _generate_book_response(self, entities: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for book_award intent"""
        return "I can help you book that award. Let me check availability and process your request."

    def _generate_availability_response(self, entities: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for check_availability intent"""
        return "Checking availability for your award options..."

    def _generate_recommend_response(self, entities: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for recommend intent"""
        program = entities.get("program", "programs")
        return f"I'll recommend the best award options from {program} based on your travel preferences."

    def _generate_explain_response(self, entities: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for explain intent"""
        topic = entities.get("query", "").replace("explain ", "").replace("what is ", "")
        return f"Let me explain {topic} for you."

class ConversationManager:
    """
    Manages conversation state and context for multi-turn interactions
    """

    def __init__(self):
        self.conversations = {}  # In production, use Redis or database

    def start_conversation(self, client_id: str) -> str:
        """Start a new conversation"""
        conversation_id = f"conv_{client_id}_{int(datetime.utcnow().timestamp())}"
        self.conversations[conversation_id] = {
            "client_id": client_id,
            "messages": [],
            "context": {},
            "start_time": datetime.utcnow().isoformat(),
            "status": "active"
        }
        return conversation_id

    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        """Add a message to the conversation"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id]["messages"].append(message)
            self.conversations[conversation_id]["context"].update(message.get("context", {}))

    def get_context(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation context"""
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]["context"]
        return {}

    def end_conversation(self, conversation_id: str) -> None:
        """End a conversation"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id]["status"] = "completed"
            self.conversations[conversation_id]["end_time"] = datetime.utcnow().isoformat()

# Singleton instances
valuation_engine = AwardValuationEngine()
nlp_processor = NLPProcessor()
conversation_manager = ConversationManager()
