import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import aiohttp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('alert_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
MAX_CONCURRENT_REQUESTS = 100
REQUEST_TIMEOUT = 30
CACHE_TTL = 300  # 5 minutes
SIMILARITY_THRESHOLD = 0.7

# In-memory cache (in production, use Redis)
class Cache:
    def __init__(self):
        self.cache = {}
        self.timestamps = {}

    def set(self, key: str, value: any):
        self.cache[key] = value
        self.timestamps[key] = time.time()

    def get(self, key: str) -> Optional[any]:
        if key in self.cache:
            if time.time() - self.timestamps[key] < CACHE_TTL:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def delete(self, key: str):
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]

cache = Cache()

# Data models
class UserProfile(BaseModel):
    user_id: str
    preferences: Dict[str, any]
    travel_history: List[Dict[str, any]]
    notification_channels: List[str]  # ['email', 'sms', 'push', 'web']
    last_updated: str

class AwardBooking(BaseModel):
    booking_id: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: datetime
    cabin_class: str
    price_in_points: int
    available_seats: int
    airline: str
    route: str
    duration_minutes: int
    booking_url: str
    created_at: datetime
    expires_at: datetime
    metadata: Dict[str, any]

class AlertMatch(BaseModel):
    user_id: str
    booking_id: str
    match_score: float
    reasons: List[str]
    notification_sent: bool = False
    sent_at: Optional[str] = None

# AI Matching Engine
class MatchingEngine:
    def __init__(self):
        # Load pre-trained models (simplified for example)
        self.route_embeddings = self._load_route_embeddings()
        self.airline_preferences = self._load_airline_preferences()

    def _load_route_embeddings(self) -> Dict[str, np.ndarray]:
        # In production, this would be a trained embedding model
        return {
            "JFK-LAX": np.random.rand(128),
            "LAX-JFK": np.random.rand(128),
            "SFO-NRT": np.random.rand(128),
            "NRT-SFO": np.random.rand(128),
            "LHR-JFK": np.random.rand(128),
            "JFK-LHR": np.random.rand(128),
        }

    def _load_airline_preferences(self) -> Dict[str, float]:
        # Airline preference scores (higher is better)
        return {
            "AA": 0.9, "DL": 0.85, "UA": 0.8, "BA": 0.95,
            "JL": 0.88, "NH": 0.82, "EK": 0.92, "QR": 0.89
        }

    def _get_route_embedding(self, route: str) -> np.ndarray:
        return self.route_embeddings.get(route, np.random.rand(128))

    def _calculate_preference_score(self, user: UserProfile, booking: AwardBooking) -> float:
        score = 0.0

        # Cabin class preference
        user_cabin = user.preferences.get('cabin_class', 'economy')
        if user_cabin == booking.cabin_class:
            score += 0.3

        # Airline preference
        airline_score = self.airline_preferences.get(booking.airline, 0.5)
        score += airline_score * 0.2

        # Route preference (using embeddings)
        route_embedding = self._get_route_embedding(booking.route)
        user_routes = [self._get_route_embedding(h['route']) for h in user.travel_history]
        if user_routes:
            similarities = cosine_similarity([route_embedding], user_routes)
            avg_similarity = np.mean(similarities)
            score += avg_similarity * 0.3

        # Price preference (lower price is better)
        user_price_range = user.preferences.get('price_range', [0, 100000])
        if user_price_range[0] <= booking.price_in_points <= user_price_range[1]:
            score += 0.2

        return min(1.0, max(0.0, score))

    def _calculate_recency_score(self, booking: AwardBooking) -> float:
        now = datetime.utcnow()
        hours_since_created = (now - booking.created_at).total_seconds() / 3600
        # More recent bookings get higher scores
        return max(0.0, 1.0 - (hours_since_created / 24))  # Decay over 24 hours

    def find_matches(self, user: UserProfile, bookings: List[AwardBooking]) -> List[AlertMatch]:
        matches = []

        for booking in bookings:
            # Skip if booking is expired
            if booking.expires_at < datetime.utcnow():
                continue

            # Calculate match score
            preference_score = self._calculate_preference_score(user, booking)
            recency_score = self._calculate_recency_score(booking)
            match_score = (preference_score * 0.7) + (recency_score * 0.3)

            if match_score >= SIMILARITY_THRESHOLD:
                # Generate reasons for the match
                reasons = []
                if preference_score >= 0.8:
                    reasons.append("High preference match")
                if recency_score >= 0.9:
                    reasons.append("Recently added booking")
                if booking.cabin_class == user.preferences.get('cabin_class'):
                    reasons.append(f"Same cabin class: {booking.cabin_class}")
                if booking.airline in self.airline_preferences:
                    reasons.append(f"Preferred airline: {booking.airline}")

                match = AlertMatch(
                    user_id=user.user_id,
                    booking_id=booking.booking_id,
                    match_score=round(match_score, 3),
                    reasons=reasons
                )
                matches.append(match)

        # Sort by match score (descending)
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:10]  # Return top 10 matches

# Real-time Alert System
class AlertSystem:
    def __init__(self):
        self.matching_engine = MatchingEngine()
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        self.pending_bookings: List[AwardBooking] = []
        self.processing = False

    async def add_user(self, user: UserProfile):
        self.user_profiles[user.user_id] = user
        logger.info(f"Added user {user.user_id} to alert system")

    async def add_booking(self, booking: AwardBooking):
        self.pending_bookings.append(booking)
        logger.info(f"Added booking {booking.booking_id} to pending queue")

        # Trigger matching if not already processing
        if not self.processing:
            self.processing = True
            asyncio.create_task(self.process_pending_bookings())

    async def process_pending_bookings(self):
        try:
            while self.pending_bookings:
                booking = self.pending_bookings.pop(0)

                # Find matching users
                matches = []
                for user in self.user_profiles.values():
                    user_matches = self.matching_engine.find_matches(user, [booking])
                    matches.extend(user_matches)

                # Send notifications to matching users
                await self.notify_users(matches)

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error processing bookings: {e}")
        finally:
            self.processing = False

    async def notify_users(self, matches: List[AlertMatch]):
        for match in matches:
            user = self.user_profiles.get(match.user_id)
            if not user:
                continue

            # Check if user is connected
            if match.user_id in self.active_connections:
                try:
                    ws = self.active_connections[match.user_id]
                    await ws.send_text(json.dumps({
                        "type": "alert_match",
                        "data": match.dict(),
                        "booking": cache.get(match.booking_id)
                    }))
                    logger.info(f"Sent alert to connected user {match.user_id}")
                except Exception as e:
                    logger.error(f"Error sending alert to {match.user_id}: {e}")
                    del self.active_connections[match.user_id]

            # Check notification channels
            for channel in user.notification_channels:
                if channel == 'web' and match.user_id not in self.active_connections:
                    continue  # Only send web notifications to connected users

                # In production, this would integrate with email/SMS services
                logger.info(f"Would send {channel} notification to {match.user_id}: {match}")

    async def connect_user(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket")

        # Send any cached alerts
        cached_alerts = cache.get(f"alerts_{user_id}")
        if cached_alerts:
            await websocket.send_text(json.dumps({
                "type": "cached_alerts",
                "data": cached_alerts
            }))

    async def disconnect_user(self, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].close()
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected")

# FastAPI Application
app = FastAPI(title="District Award Travel Alert System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize alert system
alert_system = AlertSystem()

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await alert_system.connect_user(user_id, websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await alert_system.disconnect_user(user_id)

# API Endpoints
class UserProfileRequest(BaseModel):
    user_id: str
    preferences: Dict[str, any]
    travel_history: List[Dict[str, any]]
    notification_channels: List[str]

@app.post("/api/users")
async def create_user(user: UserProfileRequest):
    user_profile = UserProfile(
        user_id=user.user_id,
        preferences=user.preferences,
        travel_history=user.travel_history,
        notification_channels=user.notification_channels,
        last_updated=datetime.utcnow().isoformat()
    )
    await alert_system.add_user(user_profile)
    return {"status": "success", "user_id": user.user_id}

class BookingRequest(BaseModel):
    booking_id: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    cabin_class: str
    price_in_points: int
    available_seats: int
    airline: str
    route: str
    duration_minutes: int
    booking_url: str
    expires_at: str
    metadata: Dict[str, any]

@app.post("/api/bookings")
async def add_booking(booking: BookingRequest):
    booking_obj = AwardBooking(
        booking_id=booking.booking_id,
        flight_number=booking.flight_number,
        departure_airport=booking.departure_airport,
        arrival_airport=booking.arrival_airport,
        departure_time=booking.departure_time,
        arrival_time=datetime.fromisoformat(booking.arrival_time),
        cabin_class=booking.cabin_class,
        price_in_points=booking.price_in_points,
        available_seats=booking.available_seats,
        airline=booking.airline,
        route=booking.route,
        duration_minutes=booking.duration_minutes,
        booking_url=booking.booking_url,
        created_at=datetime.utcnow(),
        expires_at=datetime.fromisoformat(booking.expires_at),
        metadata=booking.metadata
    )

    # Cache the booking
    cache.set(booking.booking_id, booking_obj.dict())

    # Add to alert system
    await alert_system.add_booking(booking_obj)

    return {"status": "success", "booking_id": booking.booking_id}

@app.get("/api/bookings/{booking_id}")
async def get_booking(booking_id: str):
    cached = cache.get(booking_id)
    if cached:
        return cached
    return {"error": "Booking not found"}, 404

@app.get("/api/users/{user_id}/alerts")
async def get_user_alerts(user_id: str):
    cached = cache.get(f"alerts_{user_id}")
    if cached:
        return {"alerts": cached}
    return {"alerts": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
