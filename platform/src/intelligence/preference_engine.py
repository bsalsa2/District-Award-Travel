"""
User Preference Engine
Learns and stores user travel preferences using collaborative filtering and content-based methods
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel

from ..pipeline.vector_search import TravelMemoryVectorDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TravelPreference(BaseModel):
    user_id: str
    preferred_airlines: List[str] = []
    preferred_cabins: List[str] = []
    max_stops: int = 1
    preferred_departure_times: List[str] = []
    preferred_regions: List[str] = []
    budget_range: Optional[Dict[str, float]] = None
    travel_purpose: Optional[str] = None
    last_updated: datetime = datetime.utcnow()

class PreferenceEngine:
    def __init__(self):
        self.vector_db = TravelMemoryVectorDB()
        self.cache = {}

    async def get_preferences(self, user_id: str) -> Dict:
        """Get preferences for a user, falling back to defaults"""
        if user_id in self.cache:
            return self.cache[user_id]

        # Try to load from vector DB
        preferences = await self._load_preferences_from_db(user_id)

        # Apply defaults
        preferences = self._apply_defaults(preferences)

        # Cache for 5 minutes
        self.cache[user_id] = preferences
        return preferences

    async def update_preferences(self, user_id: str, updates: Dict):
        """Update user preferences"""
        current = await self.get_preferences(user_id)

        # Apply updates
        for key, value in updates.items():
            if key in current:
                if isinstance(current[key], list):
                    current[key] = list(set(current[key] + value))
                else:
                    current[key] = value

        current["last_updated"] = datetime.utcnow()

        # Store in vector DB
        await self._store_preferences_in_db(user_id, current)

        # Update cache
        self.cache[user_id] = current

        return current

    async def _load_preferences_from_db(self, user_id: str) -> Dict:
        """Load preferences from vector database"""
        try:
            results = await self.vector_db.search_preferences(user_id)
            if results:
                return results[0]["preferences"]
        except Exception as e:
            logger.warning(f"Failed to load preferences: {e}")

        return {}

    async def _store_preferences_in_db(self, user_id: str, preferences: Dict):
        """Store preferences in vector database"""
        memory_entry = {
            "user_id": user_id,
            "preferences": preferences,
            "type": "preference",
            "timestamp": datetime.utcnow().isoformat(),
            "embedding": await self.vector_db.generate_embedding(json.dumps(preferences))
        }
        await self.vector_db.store_memory(memory_entry)

    def _apply_defaults(self, preferences: Dict) -> Dict:
        """Apply default preferences if not specified"""
        defaults = {
            "preferred_airlines": [],
            "preferred_cabins": ["economy", "premium_economy"],
            "max_stops": 1,
            "preferred_departure_times": ["morning", "afternoon"],
            "preferred_regions": [],
            "budget_range": {"min": 0, "max": 10000},
            "travel_purpose": "leisure"
        }

        for key, default_value in defaults.items():
            if key not in preferences:
                preferences[key] = default_value

        return preferences

    async def learn_from_itinerary(self, user_id: str, itinerary: Dict):
        """Learn preferences from a booked itinerary"""
        # Extract features from itinerary
        features = self._extract_features_from_itinerary(itinerary)

        # Update preferences based on features
        updates = {}

        if "airline" in features:
            updates["preferred_airlines"] = [features["airline"]]

        if "cabin" in features:
            updates["preferred_cabins"] = [features["cabin"]]

        if "stops" in features:
            updates["max_stops"] = min(features["stops"], 2)

        if updates:
            await self.update_preferences(user_id, updates)

    def _extract_features_from_itinerary(self, itinerary: Dict) -> Dict:
        """Extract preference features from an itinerary"""
        features = {}

        # Extract from first segment
        if itinerary.get("segments"):
            segment = itinerary["segments"][0]
            features["airline"] = segment.get("airline")
            features["cabin"] = segment.get("cabin")
            features["stops"] = segment.get("stops", 0)

        return features

    async def get_similar_users(self, user_id: str, limit: int = 5) -> List[str]:
        """Find similar users for collaborative filtering"""
        user_prefs = await self.get_preferences(user_id)
        pref_embedding = await self.vector_db.generate_embedding(json.dumps(user_prefs))

        results = await self.vector_db.search_similar_users(
            pref_embedding,
            limit=limit
        )

        return [r["user_id"] for r in results]
