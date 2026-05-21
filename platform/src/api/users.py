"""
User management API endpoints.
Handles registration, login, profile management, and authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

# Database path
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "district_award_travel.db")

# Security setup
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(prefix="/api/users", tags=["users"])

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    frequent_flyer_number: Optional[str] = None
    loyalty_program: Optional[str] = None
    preferred_cabin: str = "economy"
    home_airport: Optional[str] = None
    travel_style: str = "leisure"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    points_balance: int

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get the current authenticated user from JWT token."""
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

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, email, first_name, last_name FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()

    if user is None:
        raise credentials_exception
    return user

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    """Register a new user."""
    conn = get_db_connection()

    # Check if username or email already exists
    existing_user = conn.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (user.username, user.email)
    ).fetchone()

    if existing_user:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    # Hash password
    hashed_password = hash_password(user.password)

    # Insert user
    conn.execute(
        """INSERT INTO users (username, email, password_hash, first_name, last_name)
        VALUES (?, ?, ?, ?, ?)""",
        (user.username, user.email, hashed_password, user.first_name, user.last_name)
    )

    # Get user ID
    user_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    # Create user profile
    conn.execute(
        """INSERT INTO user_profiles (user_id, preferred_cabin, travel_style)
        VALUES (?, ?, ?)""",
        (user_id, "economy", "leisure")
    )

    # Create points record
    conn.execute(
        """INSERT INTO user_points (user_id, total_points)
        VALUES (?, 0)""",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return {"message": "User registered successfully"}

@router.post("/login")
async def login_user(login_data: UserLogin):
    """Authenticate user and return JWT token."""
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (login_data.username,)
    ).fetchone()
    conn.close()

    if user is None or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["id"],
        "username": user["username"]
    }

@router.get("/me")
async def read_current_user(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    conn = get_db_connection()
    user = conn.execute(
        """SELECT u.id, u.username, u.email, u.first_name, u.last_name,
        up.frequent_flyer_number, up.loyalty_program, up.preferred_cabin,
        up.home_airport, up.travel_style
        FROM users u
        LEFT JOIN user_profiles up ON u.id = up.user_id
        WHERE u.id = ?""",
        (current_user["id"],)
    ).fetchone()

    # Get points balance
    points = conn.execute(
        "SELECT total_points FROM user_points WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()

    conn.close()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "frequent_flyer_number": user["frequent_flyer_number"],
        "loyalty_program": user["loyalty_program"],
        "preferred_cabin": user["preferred_cabin"],
        "home_airport": user["home_airport"],
        "travel_style": user["travel_style"],
        "points_balance": points["total_points"] if points else 0
    }

@router.put("/profile")
async def update_profile(
    profile: UserProfile,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile."""
    conn = get_db_connection()

    # Update user profile
    conn.execute(
        """UPDATE user_profiles
        SET frequent_flyer_number = ?,
            loyalty_program = ?,
            preferred_cabin = ?,
            home_airport = ?,
            travel_style = ?
        WHERE user_id = ?""",
        (
            profile.frequent_flyer_number,
            profile.loyalty_program,
            profile.preferred_cabin,
            profile.home_airport,
            profile.travel_style,
            current_user["id"]
        )
    )

    conn.commit()
    conn.close()

    return {"message": "Profile updated successfully"}

@router.get("/points")
async def get_user_points(current_user: dict = Depends(get_current_user)):
    """Get user points balance and recent transactions."""
    conn = get_db_connection()

    # Get points balance
    points = conn.execute(
        "SELECT total_points, earned_points, redeemed_points FROM user_points WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()

    # Get recent transactions (last 10)
    transactions = conn.execute(
        """SELECT id, points, transaction_type, description, created_at
        FROM points_transactions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10""",
        (current_user["id"],)
    ).fetchall()

    conn.close()

    return {
        "balance": points["total_points"],
        "earned": points["earned_points"],
        "redeemed": points["redeemed_points"],
        "transactions": [
            {
                "id": tx["id"],
                "points": tx["points"],
                "type": tx["transaction_type"],
                "description": tx["description"],
                "date": tx["created_at"]
            } for tx in transactions
        ]
    }
