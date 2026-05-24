"""
User model definitions for District Award Travel.
Handles all user-related data structures and validation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum

class UserRole(str, Enum):
    """User roles in the system"""
    GUEST = "guest"
    MEMBER = "member"
    PREMIUM = "premium"
    ADMIN = "admin"
    AGENT = "agent"

class TravelDocumentType(str, Enum):
    """Types of travel documents"""
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    NATIONAL_ID = "national_id"
    OTHER = "other"

class LoyaltyProgram(str, Enum):
    """Supported loyalty programs"""
    AMEX_MEMBERSHIP_REWARDS = "amex_membership_rewards"
    CHASE_ULTIMATE_REWARDS = "chase_ultimate_rewards"
    CITI_THANKYOU = "citi_thankyou"
    CAPITAL_ONE_MILES = "capital_one_miles"
    DELTA_SKYMILES = "delta_skymiles"
    UNITED_MILEAGEPLUS = "united_mileageplus"
    AMERICAN_AADVANTAGE = "american_aadvantage"
    MARRIOTT_BONVOY = "marriott_bonvoy"
    HILTON_HONORS = "hilton_honors"
    IHG_REWARDS = "ihg_rewards"

class UserPreferences(BaseModel):
    """User preferences and settings"""
    theme: str = "dark"
    language: str = "en"
    currency: str = "USD"
    timezone: str = "America/New_York"
    newsletter_opt_in: bool = True
    marketing_opt_in: bool = False
    preferred_contact_method: str = "email"
    travel_notifications: bool = True
    seat_preference: str = "window"
    meal_preference: str = "standard"
    loyalty_program_priority: List[LoyaltyProgram] = [
        LoyaltyProgram.AMEX_MEMBERSHIP_REWARDS,
        LoyaltyProgram.CHASE_ULTIMATE_REWARDS
    ]

    @validator('theme')
    def validate_theme(cls, v):
        valid_themes = ['light', 'dark', 'system']
        if v not in valid_themes:
            raise ValueError(f'Theme must be one of {valid_themes}')
        return v

class TravelDocument(BaseModel):
    """Travel document information"""
    document_type: TravelDocumentType
    document_number: str
    issuing_country: str
    expiration_date: datetime
    first_name: str
    last_name: str
    issued_date: Optional[datetime] = None
    document_image_url: Optional[str] = None

    @validator('expiration_date')
    def validate_expiration(cls, v):
        if v < datetime.now():
            raise ValueError('Document cannot be expired')
        return v

class Address(BaseModel):
    """User address information"""
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    is_primary: bool = False

class ContactInfo(BaseModel):
    """User contact information"""
    primary_email: EmailStr
    secondary_email: Optional[EmailStr] = None
    phone_number: str
    secondary_phone: Optional[str] = None
    address: Address
    billing_address: Optional[Address] = None

class TravelProfile(BaseModel):
    """User travel preferences and history"""
    frequent_flyer_numbers: Dict[str, str] = {}  # airline_code: number
    hotel_program_numbers: Dict[str, str] = {}  # hotel_code: number
    car_rental_numbers: Dict[str, str] = {}  # company_code: number
    passport_number: Optional[str] = None
    known_traveler_number: Optional[str] = None
    redress_number: Optional[str] = None
    frequent_traveler_status: Dict[str, str] = {}  # airline_code: status
    preferred_airlines: List[str] = []
    preferred_hotels: List[str] = []
    preferred_car_rental: List[str] = []
    loyalty_tier: str = "standard"
    travel_alerts_enabled: bool = True

class User(BaseModel):
    """Core user model"""
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    hashed_password: str
    first_name: str
    last_name: str
    date_of_birth: Optional[datetime] = None
    role: UserRole = UserRole.MEMBER
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    preferences: UserPreferences = UserPreferences()
    contact_info: ContactInfo
    travel_profile: TravelProfile = TravelProfile()
    travel_documents: List[TravelDocument] = []
    metadata: Dict[str, Any] = {}

    @validator('username')
    def validate_username(cls, v):
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v.lower()

    @validator('is_active', 'is_verified')
    def validate_booleans(cls, v):
        return bool(v)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        allow_population_by_field_name = True

class UserCreate(BaseModel):
    """User creation model"""
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    date_of_birth: Optional[datetime] = None
    contact_info: ContactInfo

class UserUpdate(BaseModel):
    """User update model"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    date_of_birth: Optional[datetime] = None
    preferences: Optional[UserPreferences] = None
    contact_info: Optional[ContactInfo] = None
    travel_profile: Optional[TravelProfile] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    """User response model for API responses"""
    user_id: str
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    preferences: UserPreferences
    contact_info: ContactInfo
    travel_profile: TravelProfile
    travel_documents: List[TravelDocument] = []

    class Config:
        orm_mode = True
