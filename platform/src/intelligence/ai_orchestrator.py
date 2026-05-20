"""
AI Orchestrator for District Award Travel
Handles multi-modal input (voice, text, vision), context management, and award-optimized itinerary generation
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import WebSocket
from pydantic import BaseModel

from ..pipeline.award_scraper import AwardScraper
from ..pipeline.ocr_engine import OCREngine
from ..pipeline.vector_search import TravelMemoryVectorDB
from .llm_client import LLMClient
from .preference_engine import PreferenceEngine
from .voice_processor import VoiceProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TravelRequest(BaseModel):
    user_id: str
    query: str
    voice_input: Optional[str] = None
    image_data: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

class ItineraryProposal(BaseModel):
    segments: List[Dict]
    total_cost: float
    award_redemptions: int
    estimated_value: float
    confidence: float
    explanation: str

class AITravelAssistant:
    def __init__(self):
        self.voice_processor = VoiceProcessor()
        self.ocr_engine = OCREngine()
        self.award_scraper = AwardScraper()
        self.llm_client = LLMClient()
        self.preference_engine = PreferenceEngine()
        self.vector_db = TravelMemoryVectorDB()
        self.cache = {}

    async def process_request(self, request: TravelRequest) -> ItineraryProposal:
        """Main entry point for processing travel requests"""
        logger.info(f"Processing request for user {request.user_id}: {request.query}")

        # Extract context from user preferences and history
        user_context = await self._get_user_context(request.user_id)

        # Handle multi-modal input
        processed_query = await self._process_multi_modal_input(request, user_context)

        # Generate award-optimized itinerary
        itinerary = await self._generate_itinerary(processed_query, user_context)

        # Store successful itinerary in memory
        await self._store_itinerary_memory(request.user_id, itinerary)

        return itinerary

    async def _process_multi_modal_input(self, request: TravelRequest, context: Dict) -> str:
        """Process voice, text, and vision inputs"""
        combined_text = request.query

        if request.voice_input:
            text_from_voice = await self.voice_processor.transcribe(request.voice_input)
            combined_text += f" [Voice note: {text_from_voice}]"

        if request.image_data:
            ocr_text = await self.ocr_engine.process_image(request.image_data)
            combined_text += f" [Document scan: {ocr_text}]"

        # Enhance with context
        enhanced_query = await self.llm_client.enhance_query(combined_text, context)
        return enhanced_query

    async def _get_user_context(self, user_id: str) -> Dict:
        """Retrieve user preferences, history, and context"""
        preferences = self.preference_engine.get_preferences(user_id)
        history = self.vector_db.search_user_history(user_id, limit=5)
        return {"preferences": preferences, "history": history}

    async def _generate_itinerary(self, query: str, context: Dict) -> ItineraryProposal:
        """Generate award-optimized itinerary"""
        # First pass: broad search
        initial_results = await self.award_scraper.search_awards(query, limit=20)

        # Second pass: preference-aware ranking
        ranked_results = self._rank_by_preferences(initial_results, context)

        # Third pass: LLM optimization
        final_itinerary = await self.llm_client.optimize_itinerary(
            query, ranked_results, context
        )

        return final_itinerary

    def _rank_by_preferences(self, results: List[Dict], context: Dict) -> List[Dict]:
        """Rank results based on user preferences"""
        # Convert to numpy for efficient computation
        scores = np.array([
            self._calculate_preference_score(result, context)
            for result in results
        ])

        # Sort by score descending
        sorted_indices = np.argsort(-scores)
        return [results[i] for i in sorted_indices]

    def _calculate_preference_score(self, result: Dict, context: Dict) -> float:
        """Calculate preference score for a result"""
        score = 1.0  # base score

        # Apply preference weights
        prefs = context.get("preferences", {})
        if prefs.get("prefer_nonstop", False) and result.get("stops", 0) > 0:
            score *= 0.3

        if prefs.get("prefer_airline"):
            preferred_airlines = prefs["prefer_airline"]
            if result.get("airline") not in preferred_airlines:
                score *= 0.7

        if prefs.get("prefer_cabin"):
            if result.get("cabin") != prefs["prefer_cabin"]:
                score *= 0.5

        return float(score)

    async def _store_itinerary_memory(self, user_id: str, itinerary: ItineraryProposal):
        """Store successful itinerary in vector memory"""
        memory_entry = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "itinerary": itinerary.dict(),
            "embedding": await self.vector_db.generate_embedding(str(itinerary.dict()))
        }
        await self.vector_db.store_memory(memory_entry)

    async def websocket_handler(self, websocket: WebSocket):
        """Handle real-time voice and text streaming"""
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                request = TravelRequest.parse_raw(data)
                result = await self.process_request(request)
                await websocket.send_text(result.json())
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close()

# Singleton instance
ai_assistant = AITravelAssistant()
