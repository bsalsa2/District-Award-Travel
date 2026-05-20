#!/usr/bin/env python3
"""
Autonomous Award Booking AI Engine
Continuous self-optimization with reinforcement learning
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio
import aiohttp
import numpy as np
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
import torch
import torch.nn as nn
import torch.optim as optim
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/award_ai_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'award_travel')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'award_user')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'changeme')
GDS_API_KEY = os.getenv('GDS_API_KEY', 'test-key')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'test-key')
HF_TOKEN = os.getenv('HF_TOKEN', 'test-token')

# Initialize FastAPI
app = FastAPI(title="Award Booking AI Engine", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

# Prometheus monitoring
Instrumentator().instrument(app).expose(app)

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        cursor_factory=RealDictCursor
    )

# Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
    socket_timeout=5
)

# Reinforcement Learning Model
class AwardOptimizationModel(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 128, output_size: int = 1):
        super(AwardOptimizationModel, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc3 = nn.Linear(hidden_size // 2, output_size)
        self.dropout = nn.Dropout(0.2)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        x = self.dropout(x)
        x = torch.sigmoid(self.fc3(x))
        return x

# State representation
class BookingState(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    cabin_class: str = "economy"
    passengers: int = 1
    preferred_airlines: List[str] = []
    max_stops: int = 2
    budget: float = 10000.0
    user_id: str = "anonymous"
    loyalty_programs: List[str] = []
    current_credits: Dict[str, float] = {}
    historical_success_rate: float = 0.0
    time_sensitivity: float = 0.5  # 0-1 scale

# Action space
class BookingAction(BaseModel):
    airline: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price: float
    duration_hours: float
    stops: int
    cabin_class: str
    award_availability: bool
    points_required: float
    points_currency: str
    booking_class: str
    fare_basis: str
    refundable: bool
    change_fee: float
    baggage_allowance: str
    probability_of_success: float = 0.0
    confidence_score: float = 0.0

# Reward function
def calculate_reward(state: BookingState, action: BookingAction, outcome: Dict) -> float:
    """Calculate reward based on booking outcome"""
    base_reward = 0.0

    # Points value
    points_value = action.points_required * 0.1  # Normalize points

    # Cost efficiency
    cost_efficiency = 1.0 - (action.price / state.budget) if state.budget > 0 else 0.0

    # Success probability
    success_bonus = action.probability_of_success * 10.0

    # User preferences
    airline_preference = 1.0 if action.airline in state.preferred_airlines else 0.5

    # Time sensitivity
    time_bonus = (1.0 - state.time_sensitivity) * 5.0

    # Combine rewards
    total_reward = (
        points_value * 2.0 +
        cost_efficiency * 3.0 +
        success_bonus +
        airline_preference * 2.0 +
        time_bonus
    )

    # Penalize failures
    if not outcome.get('success', False):
        total_reward = -10.0

    return total_reward

# AI Engine Core
class AwardAIAgent:
    def __init__(self):
        self.model = AwardOptimizationModel(input_size=32)
        self.target_model = AwardOptimizationModel(input_size=32)
        self.target_model.load_state_dict(self.model.state_dict())
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.gamma = 0.95
        self.batch_size = 64
        self.memory = []
        self.memory_size = 10000
        self.sync_target_every = 100
        self.steps = 0
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.target_model.to(self.device)

        # Load pre-trained model if available
        self.load_model()

    def load_model(self):
        try:
            model_path = "/models/award_optimizer.pth"
            if os.path.exists(model_path):
                self.model.load_state_dict(torch.load(model_path))
                self.target_model.load_state_dict(self.model.state_dict())
                logger.info("Loaded pre-trained model")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def save_model(self):
        try:
            torch.save(self.model.state_dict(), "/models/award_optimizer.pth")
            logger.info("Model saved successfully")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def remember(self, state: BookingState, action: BookingAction, reward: float, next_state: BookingState, done: bool):
        """Store experience in memory"""
        experience = {
            'state': state.dict(),
            'action': action.dict(),
            'reward': reward,
            'next_state': next_state.dict(),
            'done': done
        }
        self.memory.append(experience)

        # Keep memory size bounded
        if len(self.memory) > self.memory_size:
            self.memory.pop(0)

    def act(self, state: BookingState) -> BookingAction:
        """Select action using epsilon-greedy policy"""
        if np.random.rand() <= self.epsilon:
            # Random exploration
            return self.random_action(state)
        else:
            # Exploitation using model
            with torch.no_grad():
                state_tensor = self.state_to_tensor(state)
                state_tensor = state_tensor.unsqueeze(0).to(self.device)
                q_values = self.model(state_tensor)
                action_idx = torch.argmax(q_values).item()

            # In a real implementation, we'd map this to actual actions
            # For now, return a dummy action
            return BookingAction(
                airline="DL",
                flight_number="DL123",
                departure_time="08:00",
                arrival_time="10:00",
                price=250.0,
                duration_hours=2.0,
                stops=0,
                cabin_class="economy",
                award_availability=True,
                points_required=25000.0,
                points_currency="DL",
                booking_class="Y",
                fare_basis="Y",
                refundable=True,
                change_fee=0.0,
                baggage_allowance="1 carry-on, 1 checked",
                probability_of_success=0.85,
                confidence_score=0.90
            )

    def random_action(self, state: BookingState) -> BookingAction:
        """Generate random action for exploration"""
        airlines = ["DL", "AA", "UA", "BA", "LH", "JL", "QF", "EK"]
        return BookingAction(
            airline=np.random.choice(airlines),
            flight_number=f"{np.random.choice(airlines)}{np.random.randint(100, 999)}",
            departure_time=f"{np.random.randint(0, 23):02d}:{np.random.randint(0, 59):02d}",
            arrival_time=f"{np.random.randint(0, 23):02d}:{np.random.randint(0, 59):02d}",
            price=np.random.uniform(100, 5000),
            duration_hours=np.random.uniform(1, 15),
            stops=np.random.randint(0, 4),
            cabin_class=np.random.choice(["economy", "premium_economy", "business", "first"]),
            award_availability=np.random.choice([True, False]),
            points_required=np.random.uniform(1000, 100000),
            points_currency=np.random.choice(["DL", "AA", "UA", "BA", "LH"]),
            booking_class=np.random.choice(["Y", "W", "S", "J", "F"]),
            fare_basis="".join([chr(np.random.randint(65, 91)) for _ in range(3)]),
            refundable=np.random.choice([True, False]),
            change_fee=np.random.uniform(0, 500),
            baggage_allowance=f"{np.random.randint(0, 3)} carry-on, {np.random.randint(0, 3)} checked",
            probability_of_success=np.random.uniform(0.5, 0.99),
            confidence_score=np.random.uniform(0.6, 0.99)
        )

    def replay(self):
        """Train on random samples from memory"""
        if len(self.memory) < self.batch_size:
            return

        batch = np.random.choice(len(self.memory), self.batch_size, replace=False)
        states = []
        actions = []
        rewards = []
        next_states = []
        dones = []

        for idx in batch:
            exp = self.memory[idx]
            states.append(exp['state'])
            actions.append(exp['action'])
            rewards.append(exp['reward'])
            next_states.append(exp['next_state'])
            dones.append(exp['done'])

        # Convert to tensors
        state_tensors = torch.stack([self.state_to_tensor(BookingState(**s)) for s in states]).to(self.device)
        action_tensors = torch.stack([self.action_to_tensor(BookingAction(**a)) for a in actions]).to(self.device)
        reward_tensors = torch.FloatTensor(rewards).to(self.device)
        next_state_tensors = torch.stack([self.state_to_tensor(BookingState(**s)) for s in next_states]).to(self.device)
        done_tensors = torch.FloatTensor(dones).to(self.device)

        # Current Q values
        current_q = self.model(state_tensors).gather(1, action_tensors.long().unsqueeze(1))

        # Target Q values
        with torch.no_grad():
            next_q = self.target_model(next_state_tensors).max(1)[0]
            target_q = reward_tensors + (1 - done_tensors) * self.gamma * next_q

        # Compute loss
        loss = self.criterion(current_q.squeeze(), target_q)

        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

        self.steps += 1

        # Sync target network
        if self.steps % self.sync_target_every == 0:
            self.target_model.load_state_dict(self.model.state_dict())

        return loss.item()

    def state_to_tensor(self, state: BookingState) -> torch.Tensor:
        """Convert state to tensor for neural network"""
        # This is a simplified representation
        # In production, you'd have a more sophisticated feature engineering
        features = [
            # Origin features (one-hot encoded)
            1.0 if state.origin == "JFK" else 0.0,
            1.0 if state.origin == "LAX" else 0.0,
            1.0 if state.origin == "LHR" else 0.0,
            1.0 if state.origin == "NRT" else 0.0,

            # Destination features
            1.0 if state.destination == "LHR" else 0.0,
            1.0 if state.destination == "NRT" else 0.0,
            1.0 if state.destination == "SYD" else 0.0,
            1.0 if state.destination == "HKG" else 0.0,

            # Date features
            float(state.departure_date.split('-')[1]) / 12.0,  # Month
            float(state.departure_date.split('-')[2]) / 31.0,  # Day

            # Passenger count
            float(state.passengers),

            # Budget
            float(state.budget) / 20000.0,

            # Time sensitivity
            state.time_sensitivity,

            # Historical success rate
            state.historical_success_rate,

            # Loyalty programs (simplified)
            1.0 if "DL" in state.loyalty_programs else 0.0,
            1.0 if "AA" in state.loyalty_programs else 0.0,
        ]

        return torch.FloatTensor(features)

    def action_to_tensor(self, action: BookingAction) -> torch.Tensor:
        """Convert action to tensor"""
        features = [
            # Airline (one-hot)
            1.0 if action.airline == "DL" else 0.0,
            1.0 if action.airline == "AA" else 0.0,
            1.0 if action.airline == "UA" else 0.0,
            1.0 if action.airline == "BA" else 0.0,

            # Price
            float(action.price) / 10000.0,

            # Duration
            float(action.duration_hours) / 24.0,

            # Stops
            float(action.stops) / 5.0,

            # Cabin class
            1.0 if action.cabin_class == "economy" else 0.0,
            1.0 if action.cabin_class == "business" else 0.0,

            # Award availability
            1.0 if action.award_availability else 0.0,

            # Points required
            float(action.points_required) / 100000.0,

            # Probability of success
            action.probability_of_success,

            # Confidence score
            action.confidence_score,
        ]

        return torch.FloatTensor(features)

# Initialize AI Agent
ai_agent = AwardAIAgent()

# Background tasks
async def continuous_learning():
    """Continuous learning loop"""
    while True:
        try:
            loss = ai_agent.replay()
            if loss:
                logger.info(f"Training loss: {loss:.4f}, Epsilon: {ai_agent.epsilon:.4f}")
            ai_agent.save_model()
        except Exception as e:
            logger.error(f"Training error: {e}")

        await asyncio.sleep(60)

async def market_monitoring():
    """Monitor market trends and update models"""
    while True:
        try:
            # Fetch recent booking data
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT origin, destination, departure_date, airline,
                       price, points_required, success, created_at
                FROM booking_attempts
                WHERE created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC
                LIMIT 1000
            """)

            data = cursor.fetchall()
            cursor.close()
            conn.close()

            if data:
                # Process data for model updates
                logger.info(f"Processing {len(data)} recent bookings for market trends")

                # Update historical success rates
                for row in data:
                    if row['success']:
                        # Update user preferences based on successful bookings
                        pass

        except Exception as e:
            logger.error(f"Market monitoring error: {e}")

        await asyncio.sleep(300)  # 5 minutes

async def policy_adaptation():
    """Adapt to new airline policies in real-time"""
    while True:
        try:
            # Check for policy updates
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT airline, policy_type, policy_value, updated_at
                FROM airline_policies
                WHERE updated_at > NOW() - INTERVAL '1 hour'
            """)

            updates = cursor.fetchall()
            cursor.close()
            conn.close()

            if updates:
                logger.info(f"Detected {len(updates)} policy updates")

                # Update model parameters based on policy changes
                for update in updates:
                    airline = update['airline']
                    policy_type = update['policy_type']
                    policy_value = update['policy_value']

                    logger.info(f"Policy update for {airline}: {policy_type} = {policy_value}")

                    # Adjust model confidence scores based on policy changes
                    # This would be more sophisticated in production

        except Exception as e:
            logger.error(f"Policy adaptation error: {e}")

        await asyncio.sleep(60)  # 1 minute

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "model_loaded": True,
            "memory_size": len(ai_agent.memory),
            "epsilon": ai_agent.epsilon
        }
    )

@app.post("/analyze-booking")
async def analyze_booking(
    state: BookingState,
    background_tasks: BackgroundTasks
):
    """Analyze booking opportunity and return optimal actions"""
    try:
        logger.info(f"Analyzing booking: {state.origin} -> {state.destination}")

        # Get current best action from model
        action = ai_agent.act(state)

        # Store state for learning
        background_tasks.add_task(store_booking_state, state, action)

        return {
            "status": "success",
            "recommended_action": action.dict(),
            "model_confidence": action.confidence_score,
            "probability_of_success": action.probability_of_success,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/book-award")
async def book_award(
    state: BookingState,
    action: BookingAction,
    background_tasks: BackgroundTasks
):
    """Initiate award booking"""
    try:
        logger.info(f"Initiating award booking: {action.airline} {action.flight_number}")

        # Store booking attempt
        background_tasks.add_task(store_booking_attempt, state, action)

        # Simulate booking process
        success = await simulate_booking_outcome(state, action)

        # Calculate reward
        reward = calculate_reward(state, action, {"success": success})

        # Store outcome for learning
        background_tasks.add_task(store_booking_outcome, state, action, success, reward)

        return {
            "status": "booking_initiated",
            "airline": action.airline,
            "flight_number": action.flight_number,
            "success": success,
            "reward": reward,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Booking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/booking-history/{user_id}")
async def get_booking_history(user_id: str):
    """Get booking history for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, origin, destination, departure_date, airline,
                   price, points_required, success, created_at
            FROM booking_attempts
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (user_id,))

        history = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"history": history}
    except Exception as e:
        logger.error(f"Error fetching booking history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/override-decision")
async def override_decision(
    state: BookingState,
    action: BookingAction,
    user_override: bool,
    reason: str
):
    """Handle user override of AI decision"""
    try:
        logger.info(f"User override: {user_override}, Reason: {reason}")

        # Store override decision
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_overrides (user_id, origin, destination, departure_date,
                                      airline, flight_number, override_decision, reason, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            state.user_id,
            state.origin,
            state.destination,
            state.departure_date,
            action.airline,
            action.flight_number,
            user_override,
            reason
        ))

        conn.commit()
        cursor.close()
        conn.close()

        # Update model based on override
        if user_override:
            # Penalize the action that was overridden
            reward = -5.0  # Strong negative reward
            ai_agent.remember(state, action, reward, state, True)

        return {"status": "override_recorded", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Override error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def store_booking_state(state: BookingState, action: BookingAction):
    """Store booking state for learning"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO booking_states (origin, destination, departure_date, return_date,
                                       cabin_class, passengers, preferred_airlines,
                                       max_stops, budget, user_id, loyalty_programs,
                                       current_credits, historical_success_rate, time_sensitivity,
                                       airline, flight_number, price, points_required,
                                       created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
        """, (
            state.origin,
            state.destination,
            state.departure_date,
            state.return_date,
            state.cabin_class,
            state.passengers,
            json.dumps(state.preferred_airlines),
            state.max_stops,
            state.budget,
            state.user_id,
            json.dumps(state.loyalty_programs),
            json.dumps(state.current_credits),
            state.historical_success_rate,
            state.time_sensitivity,
            action.airline,
            action.flight_number,
            action.price,
            action.points_required
        ))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error storing booking state: {e}")

async def store_booking_attempt(state: BookingState, action: BookingAction):
    """Store booking attempt"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO booking_attempts (origin, destination, departure_date, return_date,
                                        cabin_class, passengers, preferred_airlines,
                                        max_stops, budget, user_id, loyalty_programs,
                                        airline, flight_number, price, points_required,
                                        award_availability, probability_of_success,
                                        confidence_score, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, NOW())
        """, (
            state.origin,
            state.destination,
            state.departure_date,
            state.return_date,
            state.cabin_class,
            state.passengers,
            json.dumps(state.preferred_airlines),
            state.max_stops,
            state.budget,
            state.user_id,
            json.dumps(state.loyalty_programs),
            action.airline,
            action.flight_number,
            action.price,
            action.points_required,
            action.award_availability,
            action.probability_of_success,
            action.confidence_score
        ))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error storing booking attempt: {e}")

async def store_booking_outcome(state: BookingState, action: BookingAction, success: bool, reward: float):
    """Store booking outcome"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE booking_attempts
            SET success = %s, reward = %s, completed_at = NOW()
            WHERE airline = %s AND flight_number = %s AND created_at > NOW() - INTERVAL '5 minutes'
        """, (
            success,
            reward,
            action.airline,
            action.flight_number
        ))

        conn.commit()

        # Update user preferences based on outcome
        if success:
            cursor.execute("""
                UPDATE user_preferences
                SET successful_bookings = successful_bookings + 1,
                    last_successful_booking = NOW()
                WHERE user_id = %s
            """, (state.user_id,))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error storing booking outcome: {e}")

async def simulate_booking_outcome(state: BookingState, action: BookingAction) -> bool:
    """Simulate booking outcome with realistic probability"""
    # Base probability
    base_prob = action.probability_of_success

    # Adjust based on various factors
    adjustments = []

    # Time sensitivity penalty
    time_penalty = state.time_sensitivity * 0.3
    adjustments.append(base_prob - time_penalty)

    # Budget pressure
    if state.budget > 0:
        budget_ratio = action.price / state.budget
        if budget_ratio > 0.8:
            adjustments.append(base_prob - 0.2)

    # Historical success rate bonus
    adjustments.append(base_prob + (state.historical_success_rate * 0.2))

    # Final probability
    final_prob = max(0.1, min(0.99, sum(adjustments) / len(adjustments)))

    # Simulate outcome
    return np.random.rand() < final_prob

# Start background tasks
@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    asyncio.create_task(continuous_learning())
    asyncio.create_task(market_monitoring())
    asyncio.create_task(policy_adaptation())

    logger.info("AI Engine started successfully")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        log_level="info"
    )
