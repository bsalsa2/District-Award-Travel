"""
Authentication router for user management.
Optimized for JWT-based authentication with proper security measures.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated

# Local imports
from ...api import schemas, models, auth, database

router = APIRouter()

@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """
    Create a new user account.
    Optimized for minimal database operations.
    """
    # Check if user already exists
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    db_email = db.query(models.User).filter(
        models.User.email == user.email
    ).first()
    if db_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    db_user = models.User(
        username=user.username,
        email=user.email
    )
    db_user.password = user.password  # Uses password setter for hashing

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user

@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(database.get_db)
):
    """
    Authenticate user and return JWT token.
    Optimized for fast password verification.
    """
    # Find user by username
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()

    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
