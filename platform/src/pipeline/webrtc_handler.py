"""
WebRTC Handler for Real-time Multimodal Communication
Handles voice/video streams, transcription, and real-time AI responses
"""
import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict
import time
from datetime import datetime

import aiohttp
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import numpy as np
import websockets

from platform.src.intelligence.neural_engine import neural_engine, TravelPreferences, Itinerary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebRTCSessionManager:
    """
    Manages WebRTC sessions including signaling, media streams, and real-time processing
    """

    def __init__(self):
        self.active_sessions: Dict[str, Dict] = {}
        self.media_streams: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        self.pending_offers: Dict[str, Dict] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id

        logger.info("WebRTC Session Manager initialized")

    async def create_session(self, user_id: str, session_type: str = "audio") -> str:
        """
        Create a new WebRTC session
        Args:
            user_id: Unique user identifier
            session_type: Type of session (audio, video, or both)
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        self.active_sessions[session_id] = {
            "user_id": user_id,
            "session_type": session_type,
            "created_at": datetime.now().isoformat(),
            "status": "initializing",
            "ice_candidates": [],
            "data_channel_ready": False,
            "audio_received": False,
            "video_received": False,
            "last_activity": time.time()
        }

        self.user_sessions[user_id] = session_id

        logger.info(f"Created new session {session_id} for user {user_id}")

        return session_id

    async def add_ice_candidate(self, session_id: str, candidate: Dict):
        """Add ICE candidate to session"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["ice_candidates"].append(candidate)
            logger.debug(f"Added ICE candidate to session {session_id}")
        else:
            logger.warning(f"Session {session_id} not found")

    async def set_session_ready(self, session_id: str, data_channel_ready: bool = False):
        """Mark session as ready for data transfer"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = "ready"
            self.active_sessions[session_id]["data_channel_ready"] = data_channel_ready
            self.active_sessions[session_id]["last_activity"] = time.time()
            logger.info(f"Session {session_id} marked as ready")
        else:
            logger.warning(f"Session {session_id} not found")

    async def receive_media(self, session_id: str, media_type: str, data: bytes):
        """
        Receive media data (audio or video)
        Args:
            session_id: Session ID
            media_type: Type of media (audio or video)
            data: Media data
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found")
            return

        self.active_sessions[session_id][f"{media_type}_received"] = True
        self.active_sessions[session_id]["last_activity"] = time.time()

        # Process audio data in real-time
        if media_type == "audio" and data:
            try:
                # Process voice input through neural engine
                transcription = neural_engine.process_voice_input(data)

                if transcription:
                    logger.info(f"Transcription from session {session_id}: {transcription[:100]}...")

                    # Store transcription temporarily
                    if "transcriptions" not in self.active_sessions[session_id]:
                        self.active_sessions[session_id]["transcriptions"] = []

                    self.active_sessions[session_id]["transcriptions"].append({
                        "text": transcription,
                        "timestamp": datetime.now().isoformat(),
                        "processed": False
                    })

            except Exception as e:
                logger.error(f"Error processing audio in session {session_id}: {e}")

    async def process_transcriptions(self, session_id: str):
        """
        Process accumulated transcriptions through the neural engine
        """
        if session_id not in self.active_sessions:
            return

        transcriptions = self.active_sessions[session_id].get("transcriptions", [])

        for transcription in transcriptions:
            if not transcription.get("processed", False):
                try:
                    # Extract preferences from transcription
                    preferences = neural_engine.process_text_input(transcription["text"])

                    # Cache preferences
                    user_id = self.active_sessions[session_id]["user_id"]
                    neural_engine.cache_preferences(user_id, preferences)

                    # Generate itineraries
                    itineraries = neural_engine.generate_itineraries(preferences)

                    # Store results
                    self.active_sessions[session_id]["preferences"] = asdict(preferences)
                    self.active_sessions[session_id]["itineraries"] = [
                        {
                            "id": itin.id,
                            "title": itin.title,
                            "description": itin.description,
                            "total_points": itin.total_points,
                            "total_cash": itin.total_cash,
                            "best_option": asdict(itin.flights[itin.best_option_index]) if itin.flights else None,
                            "trade_off_explanation": itin.trade_off_explanation
                        }
                        for itin in itineraries
                    ]

                    transcription["processed"] = True
                    logger.info(f"Processed transcription for session {session_id}")

                except Exception as e:
                    logger.error(f"Error processing transcription: {e}")

    async def send_response(self, session_id: str, message: Dict):
        """
        Send response back to client via WebSocket or data channel
        Args:
            session_id: Session ID
            message: Message to send
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found")
            return

        user_id = self.active_sessions[session_id]["user_id"]

        # Try to send via WebSocket if connected
        if user_id in self.websocket_connections:
            try:
                websocket = self.websocket_connections[user_id]
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                    logger.debug(f"Sent message to user {user_id} via WebSocket")
                    return
            except Exception as e:
                logger.error(f"Error sending via WebSocket: {e}")
                # Remove dead connection
                del self.websocket_connections[user_id]

        # If no WebSocket, store in session for later retrieval
        if "pending_responses" not in self.active_sessions[session_id]:
            self.active_sessions[session_id]["pending_responses"] = []

        self.active_sessions[session_id]["pending_responses"].append(message)
        logger.debug(f"Stored response for session {session_id}")

    async def get_session_status(self, session_id: str) -> Dict:
        """Get current session status"""
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}

        session = self.active_sessions[session_id]

        return {
            "session_id": session_id,
            "status": session["status"],
            "session_type": session["session_type"],
            "created_at": session["created_at"],
            "last_activity": session["last_activity"],
            "has_transcriptions": len(session.get("transcriptions", [])) > 0,
            "has_itineraries": "itineraries" in session,
            "preferences": session.get("preferences"),
            "itineraries": session.get("itineraries", []),
            "ice_candidates_count": len(session["ice_candidates"]),
            "data_channel_ready": session["data_channel_ready"]
        }

    async def cleanup_session(self, session_id: str):
        """Clean up a session"""
        if session_id in self.active_sessions:
            user_id = self.active_sessions[session_id]["user_id"]

            # Remove from user mapping
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]

            # Remove from active sessions
            del self.active_sessions[session_id]

            logger.info(f"Cleaned up session {session_id}")

    async def heartbeat(self):
        """Periodic heartbeat to clean up stale sessions"""
        while True:
            current_time = time.time()
            stale_sessions = []

            for session_id, session in self.active_sessions.items():
                if current_time - session["last_activity"] > 3600:  # 1 hour timeout
                    stale_sessions.append(session_id)

            for session_id in stale_sessions:
                await self.cleanup_session(session_id)

            await asyncio.sleep(60)  # Check every minute

# Global session manager instance
session_manager = WebRTCSessionManager()

async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time communication
    Handles signaling and data exchange
    """
    await websocket.accept()
    session_manager.websocket_connections[user_id] = websocket

    try:
        while True:
            try:
                data = await websocket.receive_json()

                if "type" not in data:
                    continue

                if data["type"] == "create_session":
                    session_id = await session_manager.create_session(user_id, data.get("session_type", "audio"))
                    await websocket.send_json({
                        "type": "session_created",
                        "session_id": session_id,
                        "status": "success"
                    })

                elif data["type"] == "ice_candidate":
                    await session_manager.add_ice_candidate(data["session_id"], data["candidate"])
                    await websocket.send_json({
                        "type": "ice_candidate_received",
                        "status": "success"
                    })

                elif data["type"] == "session_ready":
                    await session_manager.set_session_ready(data["session_id"], data.get("data_channel_ready", False))
                    await websocket.send_json({
                        "type": "session_ready_ack",
                        "status": "success"
                    })

                elif data["type"] == "media_data":
                    await session_manager.receive_media(data["session_id"], data["media_type"], data["data"])
                    await websocket.send_json({
                        "type": "media_received",
                        "status": "success"
                    })

                elif data["type"] == "get_status":
                    status = await session_manager.get_session_status(data["session_id"])
                    await websocket.send_json({
                        "type": "status_response",
                        "data": status
                    })

                elif data["type"] == "process_transcriptions":
                    await session_manager.process_transcriptions(data["session_id"])
                    status = await session_manager.get_session_status(data["session_id"])
                    await websocket.send_json({
                        "type": "transcriptions_processed",
                        "data": status
                    })

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket handler: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    finally:
        # Cleanup
        if user_id in session_manager.websocket_connections:
            del session_manager.websocket_connections[user_id]
        await session_manager.cleanup_session(session_manager.user_sessions.get(user_id, ""))

# Export for use in FastAPI
__all__ = ['websocket_endpoint', 'session_manager']
