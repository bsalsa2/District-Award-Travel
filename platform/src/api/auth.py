"""
Authentication utilities using JWT.
Optimized for performance with proper token handling.
"""

from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session
from . import models, schemas
import os

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "district-award-travel-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT access token.
    Optimized for minimal overhead.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, db: Session) -> models.User:
    """
    Verify JWT token and return user.
    Optimized for fast validation.
    """
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
    except InvalidTokenError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(lambda: next(get_db()))
):
    """
    Dependency to get current authenticated user.
    """
    return verify_token(token, db)

def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    """
    Dependency to ensure user is active.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
