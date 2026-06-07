"""
Main FastAPI application for District Award Travel
Handles award flight booking and user profile management
"""
import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional, Dict
import sqlite3
import json
import logging
from datetime import datetime, timedelta
import uuid
import hashlib
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security configurations
SECRET_KEY = os.getenv("SECRET_KEY", "district-award-travel-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(
    title="District Award Travel API",
    description="Award flight booking and user profile management system",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection manager
class DatabaseManager:
    def __init__(self):
        self.db_path = os.getenv("DATABASE_URL", "platform/database.db")
        self._init_db()

    def _init_db(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

            # User profiles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    award_points INTEGER DEFAULT 0,
                    tier_level TEXT DEFAULT 'bronze',
                    frequent_flyer_number TEXT,
                    date_of_birth TEXT,
                    phone_number TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            # Flights table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flights (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    airline TEXT NOT NULL,
                    flight_number TEXT NOT NULL,
                    departure_airport TEXT NOT NULL,
                    arrival_airport TEXT NOT NULL,
                    departure_time TIMESTAMP NOT NULL,
                    arrival_time TIMESTAMP NOT NULL,
                    booking_reference TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    cabin_class TEXT,
                    award_points_used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            # Award points transactions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS award_transactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT,
                    reference_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            # Points redemption rules
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS redemption_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airline TEXT NOT NULL,
                    cabin_class TEXT NOT NULL,
                    points_required INTEGER NOT NULL,
                    distance_miles INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(airline, cabin_class)
                )
            """)

            # Insert sample redemption rules if empty
            cursor.execute("SELECT COUNT(*) FROM redemption_rules")
            if cursor.fetchone()[0] == 0:
                redemption_rules = [
                    ("AA", "economy", 25000, 2500),
                    ("AA", "business", 50000, 2500),
                    ("DL", "economy", 30000, 3000),
                    ("DL", "business", 60000, 3000),
                    ("UA", "economy", 28000, 2800),
                    ("UA", "business", 55000, 2800),
                    ("BA", "economy", 40000, 4000),
                    ("BA", "business", 80000, 4000),
                ]
                cursor.executemany(
                    "INSERT INTO redemption_rules (airline, cabin_class, points_required, distance_miles) VALUES (?, ?, ?, ?)",
                    redemption_rules
                )

            conn.commit()

    def get_connection(self):
        """Get a database connection"""
        return sqlite3.connect(self.db_path)

# Initialize database
db_manager = DatabaseManager()

# Models
class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True

class UserProfile(BaseModel):
    award_points: int
    tier_level: str
    frequent_flyer_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone_number: Optional[str] = None

class FlightBase(BaseModel):
    airline: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    cabin_class: str
    booking_reference: str

class FlightCreate(FlightBase):
    award_points_used: Optional[int] = 0

class Flight(FlightBase):
    id: str
    user_id: str
    status: str
    created_at: datetime

    class Config:
        orm_mode = True

class AwardTransaction(BaseModel):
    points: int
    transaction_type: str
    description: str
    reference_id: Optional[str] = None

class RedemptionRule(BaseModel):
    airline: str
    cabin_class: str
    points_required: int
    distance_miles: int
    is_active: bool

# Utility functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()

        if user_data:
            user_dict = {
                "id": user_data[0],
                "username": user_data[1],
                "email": user_data[2],
                "hashed_password": user_data[3],
                "full_name": user_data[4],
                "created_at": user_data[5],
                "updated_at": user_data[6],
                "is_active": bool(user_data[7])
            }
            return User(**user_dict)
    return None

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()

        if user_data is None:
            raise credentials_exception

        user_dict = {
            "id": user_data[0],
            "username": user_data[1],
            "email": user_data[2],
            "hashed_password": user_data[3],
            "full_name": user_data[4],
            "created_at": user_data[5],
            "updated_at": user_data[6],
            "is_active": bool(user_data[7])
        }
        return User(**user_dict)

# API Endpoints
@app.post("/token", response_model=dict)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(db_manager, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=User)
async def create_user(user: UserCreate):
    """Create a new user"""
    hashed_password = get_password_hash(user.password)

    user_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (id, username, email, hashed_password, full_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, user.username, user.email, hashed_password, user.full_name, created_at, created_at)
            )

            # Create user profile with initial points
            cursor.execute(
                "INSERT INTO user_profiles (user_id, award_points) VALUES (?, 0)",
                (user_id,)
            )

            conn.commit()
            logger.info(f"User created: {user.username}")
            return User(
                id=user_id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=True,
                created_at=created_at
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@app.get("/users/me/profile", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get user profile with award points"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (current_user.id,))
        profile_data = cursor.fetchone()

        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        return UserProfile(
            award_points=profile_data[1],
            tier_level=profile_data[2],
            frequent_flyer_number=profile_data[3],
            date_of_birth=profile_data[4],
            phone_number=profile_data[5]
        )

@app.put("/users/me/profile", response_model=UserProfile)
async def update_user_profile(
    profile: UserProfile,
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET
                award_points = award_points,  -- Keep existing points
                tier_level = ?,
                frequent_flyer_number = ?,
                date_of_birth = ?,
                phone_number = ?
            WHERE user_id = ?
        """, (
            profile.tier_level,
            profile.frequent_flyer_number,
            profile.date_of_birth,
            profile.phone_number,
            current_user.id
        ))

        conn.commit()
        logger.info(f"User profile updated: {current_user.username}")
        return profile

@app.post("/flights/", response_model=Flight)
async def book_flight(
    flight: FlightCreate,
    current_user: User = Depends(get_current_user)
):
    """Book an award flight"""
    # Calculate points needed based on airline and cabin class
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Get points required for this flight
        cursor.execute("""
            SELECT points_required
            FROM redemption_rules
            WHERE airline = ? AND cabin_class = ?
        """, (flight.airline, flight.cabin_class))

        rule = cursor.fetchone()
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No redemption rule found for {flight.airline} {flight.cabin_class}"
            )

        points_required = rule[0]

        # Check if user has enough points
        cursor.execute("""
            SELECT award_points FROM user_profiles WHERE user_id = ?
        """, (current_user.id,))
        user_points = cursor.fetchone()[0]

        if user_points < points_required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient award points. Required: {points_required}, Available: {user_points}"
            )

        # Create flight booking
        flight_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO flights (
                id, user_id, airline, flight_number, departure_airport, arrival_airport,
                departure_time, arrival_time, booking_reference, cabin_class, award_points_used, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            flight_id, current_user.id, flight.airline, flight.flight_number,
            flight.departure_airport, flight.arrival_airport,
            flight.departure_time.isoformat(), flight.arrival_time.isoformat(),
            flight.booking_reference, flight.cabin_class, points_required, created_at
        ))

        # Deduct points from user
        new_points = user_points - points_required
        cursor.execute("""
            UPDATE user_profiles SET award_points = ? WHERE user_id = ?
        """, (new_points, current_user.id))

        # Record transaction
        transaction_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO award_transactions (
                id, user_id, points, transaction_type, description, reference_id
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            transaction_id, current_user.id, -points_required,
            "redemption", f"Award flight: {flight.airline} {flight.flight_number}",
            flight_id
        ))

        conn.commit()
        logger.info(f"Flight booked: {flight.airline} {flight.flight_number} for user {current_user.username}")

        return Flight(
            id=flight_id,
            user_id=current_user.id,
            airline=flight.airline,
            flight_number=flight.flight_number,
            departure_airport=flight.departure_airport,
            arrival_airport=flight.arrival_airport,
            departure_time=flight.departure_time,
            arrival_time=flight.arrival_time,
            booking_reference=flight.booking_reference,
            cabin_class=flight.cabin_class,
            award_points_used=points_required,
            status="confirmed",
            created_at=created_at
        )

@app.get("/flights/", response_model=List[Flight])
async def get_user_flights(
    current_user: User = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0
):
    """Get user's flight history"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM flights
            WHERE user_id = ?
            ORDER BY departure_time DESC
            LIMIT ? OFFSET ?
        """, (current_user.id, limit, offset))

        flights = []
        for row in cursor.fetchall():
            flight_dict = {
                "id": row[0],
                "user_id": row[1],
                "airline": row[2],
                "flight_number": row[3],
                "departure_airport": row[4],
                "arrival_airport": row[5],
                "departure_time": datetime.fromisoformat(row[6]),
                "arrival_time": datetime.fromisoformat(row[7]),
                "booking_reference": row[8],
                "status": row[9],
                "cabin_class": row[10],
                "award_points_used": row[11],
                "created_at": datetime.fromisoformat(row[12])
            }
            flights.append(Flight(**flight_dict))

        return flights

@app.get("/flights/{booking_reference}", response_model=Flight)
async def get_flight_details(
    booking_reference: str,
    current_user: User = Depends(get_current_user)
):
    """Get details for a specific flight booking"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM flights
            WHERE booking_reference = ? AND user_id = ?
        """, (booking_reference, current_user.id))

        flight_data = cursor.fetchone()
        if not flight_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found"
            )

        flight_dict = {
            "id": flight_data[0],
            "user_id": flight_data[1],
            "airline": flight_data[2],
            "flight_number": flight_data[3],
            "departure_airport": flight_data[4],
            "arrival_airport": flight_data[5],
            "departure_time": datetime.fromisoformat(flight_data[6]),
            "arrival_time": datetime.fromisoformat(flight_data[7]),
            "booking_reference": flight_data[8],
            "status": flight_data[9],
            "cabin_class": flight_data[10],
            "award_points_used": flight_data[11],
            "created_at": datetime.fromisoformat(flight_data[12])
        }

        return Flight(**flight_dict)

@app.get("/award-points/transactions", response_model=List[AwardTransaction])
async def get_award_transactions(
    current_user: User = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0
):
    """Get user's award points transactions"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM award_transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (current_user.id, limit, offset))

        transactions = []
        for row in cursor.fetchall():
            transaction_dict = {
                "id": row[0],
                "user_id": row[1],
                "points": row[2],
                "transaction_type": row[3],
                "description": row[4],
                "reference_id": row[5],
                "created_at": datetime.fromisoformat(row[6])
            }
            transactions.append(AwardTransaction(**transaction_dict))

        return transactions

@app.get("/award-points/balance", response_model=dict)
async def get_award_points_balance(
    current_user: User = Depends(get_current_user)
):
    """Get user's current award points balance"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT award_points FROM user_profiles WHERE user_id = ?
        """, (current_user.id,))

        points = cursor.fetchone()[0]

        return {"award_points": points}

@app.get("/redemption-rules", response_model=List[RedemptionRule])
async def get_redemption_rules():
    """Get all active redemption rules"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM redemption_rules WHERE is_active = 1")

        rules = []
        for row in cursor.fetchall():
            rule_dict = {
                "airline": row[1],
                "cabin_class": row[2],
                "points_required": row[3],
                "distance_miles": row[4],
                "is_active": bool(row[5])
            }
            rules.append(RedemptionRule(**rule_dict))

        return rules

@app.post("/award-points/earn", response_model=AwardTransaction)
async def earn_award_points(
    points: int,
    description: str,
    current_user: User = Depends(get_current_user)
):
    """Manually add award points to user account"""
    if points <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points must be positive"
        )

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Get current points
        cursor.execute("""
            SELECT award_points FROM user_profiles WHERE user_id = ?
        """, (current_user.id,))
        current_points = cursor.fetchone()[0]

        # Update points
        new_points = current_points + points
        cursor.execute("""
            UPDATE user_profiles SET award_points = ? WHERE user_id = ?
        """, (new_points, current_user.id))

        # Record transaction
        transaction_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO award_transactions (
                id, user_id, points, transaction_type, description
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            transaction_id, current_user.id, points,
            "earn", description
        ))

        conn.commit()
        logger.info(f"Added {points} points to user {current_user.username}")

        return AwardTransaction(
            id=transaction_id,
            user_id=current_user.id,
            points=points,
            transaction_type="earn",
            description=description,
            created_at=datetime.utcnow().isoformat()
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
