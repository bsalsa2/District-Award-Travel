"""
LLM Client for Travel Itinerary Generation
Uses NVIDIA NeMo for optimized travel-specific LLM inference
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional

import numpy as np
from nemo.collections.nlp.models import PunctuationCapitalizationModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        # Load travel-optimized LLM
        self.tokenizer = AutoTokenizer.from_pretrained(
            "nvidia/llama3-travel-optimized",
            use_fast=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            "nvidia/llama3-travel-optimized",
            device_map="auto",
            torch_dtype="auto"
        )

        # Load punctuation/capitalization model
        self.punct_model = PunctuationCapitalizationModel.from_pretrained(
            "nvidia/llama3-punct-cap"
        )

    async def enhance_query(self, query: str, context: Dict) -> str:
        """Enhance user query with context and structure"""
        enhanced = f"""
        User Query: {query}

        User Context:
        - Preferred Airlines: {context.get('preferences', {}).get('preferred_airlines', [])}
        - Preferred Cabins: {context.get('preferences', {}).get('preferred_cabins', [])}
        - Max Stops: {context.get('preferences', {}).get('max_stops', 1)}
        - Travel Purpose: {context.get('preferences', {}).get('travel_purpose', 'leisure')}
        - Recent Trips: {len(context.get('history', []))} previous trips

        Please enhance this query to be more specific and actionable for award travel planning.
        Focus on:
        1. Departure and arrival cities/airports
        2. Travel dates (month/season)
        3. Special occasions or preferences
        4. Award program preferences
        """

        inputs = self.tokenizer(enhanced, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=128)
        enhanced_query = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        return enhanced_query.strip()

    async def optimize_itinerary(self, query: str, raw_results: List[Dict], context: Dict) -> Dict:
        """Optimize itinerary using LLM"""
        # Format raw results
        formatted_results = self._format_results_for_llm(raw_results)

        prompt = f"""
        Original Query: {query}

        Available Award Options:
        {formatted_results}

        User Context:
        {json.dumps(context.get('preferences', {}), indent=2)}

        Please create the optimal itinerary that:
        1. Maximizes award redemptions and value
        2. Respects user preferences (airlines, cabins, max stops)
        3. Provides a logical routing with reasonable connection times
        4. Includes estimated values for each segment
        5. Returns a confidence score (0-1) for the recommendation

        Return in JSON format with these fields:
        {{
            "segments": [{{"departure": "...", "arrival": "...", "airline": "...", "flight_number": "...", "departure_time": "...", "arrival_time": "...", "cabin": "...", "award_cost": X, "estimated_value": X}}],
            "total_cost": X,
            "award_redemptions": X,
            "estimated_value": X,
            "confidence": X,
            "explanation": "..."
        }}
        """

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.3,
            top_p=0.9
        )

        result_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Parse JSON from response
        try:
            result = json.loads(result_text)
            return result
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            # Fallback to simple format
            return self._fallback_itinerary(raw_results, context)

    def _format_results_for_llm(self, results: List[Dict]) -> str:
        """Format raw results for LLM consumption"""
        formatted = []
        for i, result in enumerate(results[:10]):  # Top 10 results
            formatted.append(f"""
            Option {i+1}:
            - Route: {result.get('departure_airport')} -> {result.get('arrival_airport')}
            - Airline: {result.get('airline')}
            - Flight: {result.get('flight_number')}
            - Cabin: {result.get('cabin')}
            - Stops: {result.get('stops', 0)}
            - Award Cost: {result.get('award_cost', 0)} points
            - Cash Price: ${result.get('cash_price', 0)}
            - Estimated Value: ${result.get('estimated_value', 0)}
            - Departure: {result.get('departure_time')}
            - Arrival: {result.get('arrival_time')}
            """)
        return "\n".join(formatted)

    def _fallback_itinerary(self, raw_results: List[Dict], context: Dict) -> Dict:
        """Create a simple itinerary as fallback"""
        if not raw_results:
            return {
                "segments": [],
                "total_cost": 0,
                "award_redemptions": 0,
                "estimated_value": 0,
                "confidence": 0,
                "explanation": "No award options found"
            }

        # Select best option based on simple heuristics
        best = raw_results[0]
        return {
            "segments": [{
                "departure": best.get("departure_airport"),
                "arrival": best.get("arrival_airport"),
                "airline": best.get("airline"),
                "flight_number": best.get("flight_number"),
                "departure_time": best.get("departure_time"),
                "arrival_time": best.get("arrival_time"),
                "cabin": best.get("cabin"),
                "award_cost": best.get("award_cost", 0),
                "estimated_value": best.get("estimated_value", 0)
            }],
            "total_cost": best.get("award_cost", 0),
            "award_redemptions": 1,
            "estimated_value": best.get("estimated_value", 0),
            "confidence": 0.8,
            "explanation": "Selected best available award option"
        }

    async def generate_explanation(self, itinerary: Dict) -> str:
        """Generate human-readable explanation of itinerary"""
        prompt = f"""
        Itinerary Details:
        {json.dumps(itinerary, indent=2)}

        Generate a clear, friendly explanation suitable for a travel advisor to explain to a customer.
        Include:
        - Route summary
        - Award redemptions used
        - Estimated value of the award
        - Any special notes or considerations
        - Connection details if applicable

        Keep it concise but informative.
        """

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=256)
        explanation = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        return explanation.strip()

    async def correct_grammar(self, text: str) -> str:
        """Correct grammar and punctuation in text"""
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=64)
        corrected = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Also apply punctuation model
        punct_corrected = self.punct_model.add_punctuation(corrected)

        return punct_corrected.strip()
