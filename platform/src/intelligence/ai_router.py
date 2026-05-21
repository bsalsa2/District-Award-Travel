"""
FastAPI router for AI-powered award travel assistant endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from platform.src.intelligence.ai_models import (
    AwardValuationEngine,
    NLPProcessor,
    conversation_manager
)
from platform.src.database.models import AwardRecommendation, Conversation
from platform.src.database import get_db
from sqlalchemy.orm import Session
from platform.src.observability.metrics import track_metric
from platform.src.observability.tracing import trace_span

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Assistant"])

# Initialize AI models
valuation_engine = AwardValuationEngine()
nlp_processor = NLPProcessor()

class NLURequest(BaseModel):
    """Request model for Natural Language Understanding"""
    query: str
    client_id: str
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class NLUResponse(BaseModel):
    """Response model for Natural Language Understanding"""
    intent: str
    entities: Dict[str, Any]
    response: str
    confidence: float
    conversation_id: str
    timestamp: str

class AwardValueRequest(BaseModel):
    """Request model for award value calculation"""
    program: str
    points: int
    cabin: str = "economy"
    partner: bool = False
    season: str = "off_peak"

class AwardValueResponse(BaseModel):
    """Response model for award value calculation"""
    program: str
    points: int
    cabin: str
    calculated_value: float
    currency: str = "USD"
    explanation: str

class RecommendationRequest(BaseModel):
    """Request model for award recommendations"""
    client_id: str
    destination: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    cabin: str = "economy"
    budget: Optional[float] = None
    programs: Optional[List[str]] = None
    max_points: Optional[int] = None

class RecommendationResponse(BaseModel):
    """Response model for award recommendations"""
    recommendations: List[Dict[str, Any]]
    total_results: int
    query_time: str
    conversation_id: str

@router.post("/nlu", response_model=NLUResponse)
@trace_span("ai_nlu_endpoint")
async def process_natural_language(request: NLURequest):
    """
    Process natural language query and extract intent and entities

    Args:
        request: NLURequest containing the query and context

    Returns:
        NLUResponse with intent, entities, and generated response
    """
    try:
        # Start or continue conversation
        if request.conversation_id:
            conversation_id = request.conversation_id
        else:
            conversation_id = conversation_manager.start_conversation(request.client_id)

        # Extract intent and entities
        intent_data = nlp_processor.extract_intent(request.query)

        # Generate response
        response_text = nlp_processor.generate_response(intent_data, request.context or {})

        # Calculate confidence (simple heuristic)
        confidence = 0.85  # In production, use ML model

        track_metric("nlu_processed", {
            "intent": intent_data["intent"],
            "confidence": confidence
        })

        return {
            "intent": intent_data["intent"],
            "entities": intent_data["entities"],
            "response": response_text,
            "confidence": confidence,
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing NLU: {str(e)}")
        track_metric("nlu_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calculate-value", response_model=AwardValueResponse)
@trace_span("ai_value_calculation")
async def calculate_award_value(request: AwardValueRequest):
    """
    Calculate the monetary value of award points/redemption

    Args:
        request: AwardValueRequest with award details

    Returns:
        AwardValueResponse with calculated value
    """
    try:
        award_data = {
            "program": request.program,
            "points": request.points,
            "cabin": request.cabin,
            "partner": request.partner,
            "season": request.season
        }

        value = valuation_engine.calculate_award_value(award_data)

        explanation = f"Based on {request.points:,} {request.program.upper()} points in {request.cabin} class, the estimated value is ${value:,.2f}"

        track_metric("award_value_calculated", {
            "program": request.program,
            "points": request.points,
            "value": value
        })

        return {
            "program": request.program,
            "points": request.points,
            "cabin": request.cabin,
            "calculated_value": value,
            "currency": "USD",
            "explanation": explanation
        }

    except Exception as e:
        logger.error(f"Error calculating award value: {str(e)}")
        track_metric("value_calculation_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recommend", response_model=RecommendationResponse)
@trace_span("ai_recommendation_endpoint")
async def get_award_recommendations(request: RecommendationRequest):
    """
    Get personalized award travel recommendations

    Args:
        request: RecommendationRequest with user preferences

    Returns:
        RecommendationResponse with ranked recommendations
    """
    try:
        # In production, this would query a database or external APIs
        # For now, return mock data based on request

        # Start conversation
        conversation_id = conversation_manager.start_conversation(request.client_id)

        # Generate mock recommendations based on criteria
        mock_recommendations = []

        programs = request.programs or ["aa", "dl", "ua"]
        destinations = request.destination.split(",") if request.destination else ["New York", "Los Angeles", "Chicago"]

        for program in programs:
            for dest in destinations[:2]:  # Limit to 2 destinations for demo
                points_range = [50000, 75000, 100000]
                for points in points_range:
                    award_data = {
                        "program": program,
                        "points": points,
                        "cabin": request.cabin,
                        "destination": dest,
                        "value": valuation_engine.calculate_award_value({
                            "program": program,
                            "points": points,
                            "cabin": request.cabin
                        }),
                        "currency": "USD",
                        "description": f"Round trip to {dest} in {request.cabin.replace('_', ' ')} class",
                        "conditions": {"blackout_dates": False, "partner_airline": True},
                        "availability": {"seats": 5, "book_by": (datetime.utcnow() + timedelta(days=30)).isoformat()}
                    }
                    mock_recommendations.append(award_data)

        # Rank by value
        ranked = valuation_engine.get_award_comparison(mock_recommendations)

        track_metric("recommendations_generated", {
            "client_id": request.client_id,
            "count": len(ranked),
            "programs": programs
        })

        return {
            "recommendations": ranked[:10],  # Return top 10
            "total_results": len(ranked),
            "query_time": datetime.utcnow().isoformat(),
            "conversation_id": conversation_id
        }

    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        track_metric("recommendation_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compare", response_model=List[Dict[str, Any]])
@trace_span("ai_comparison_endpoint")
async def compare_awards(awards: List[Dict[str, Any]]):
    """
    Compare multiple award options and rank them by value

    Args:
        awards: List of award dictionaries

    Returns:
        List of ranked awards
    """
    try:
        ranked = valuation_engine.get_award_comparison(awards)

        track_metric("awards_compared", {"count": len(awards)})

        return ranked

    except Exception as e:
        logger.error(f"Error comparing awards: {str(e)}")
        track_metric("comparison_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversation/{conversation_id}")
@trace_span("ai_get_conversation")
async def get_conversation(conversation_id: str):
    """
    Retrieve conversation history

    Args:
        conversation_id: ID of the conversation

    Returns:
        Conversation history
    """
    try:
        context = conversation_manager.get_context(conversation_id)
        return {
            "conversation_id": conversation_id,
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error retrieving conversation: {str(e)}")
        raise HTTPException(status_code=404, detail="Conversation not found")
