# backend/models/user.py
"""
User data models and schemas.
Defines user-related data structures for the application.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class UserRole(str, Enum):
    """User role enumeration."""
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"


class UserPreferences(BaseModel):
    """User preferences for the application."""
    summary_length: str = "medium"  # short, medium, long
    summary_style: str = "abstractive"  # extractive, abstractive
    simplify_technical: bool = False
    preferred_sections: List[str] = ["abstract", "results", "conclusions"]
    language: str = "en"
    
    class Config:
        schema_extra = {
            "example": {
                "summary_length": "medium",
                "summary_style": "abstractive",
                "simplify_technical": True,
                "preferred_sections": ["abstract", "results"],
                "language": "en"
            }
        }


class UserBase(BaseModel):
    """Base user schema with common attributes."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    is_active: bool = True
    role: UserRole = UserRole.USER
    preferences: UserPreferences = Field(default_factory=UserPreferences)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8)
    
    @validator('password')
    def validate_password(cls, v):
        """Ensure password meets security requirements."""
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        return v


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    preferences: Optional[UserPreferences] = None


class UserInDB(UserBase):
    """User schema as stored in database."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    email_verified: bool = False
    
    # Usage statistics
    documents_uploaded: int = 0
    summaries_generated: int = 0
    api_calls_count: int = 0
    storage_used_mb: float = 0.0
    
    # Subscription info
    subscription_tier: str = "free"
    subscription_expires: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserResponse(UserBase):
    """User schema for API responses (excludes sensitive data)."""
    id: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    email_verified: bool
    documents_uploaded: int
    summaries_generated: int
    subscription_tier: str
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserLogin(BaseModel):
    """Schema for user login."""
    username_or_email: str
    password: str


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""
    user_id: str
    username: str
    email: str
    role: UserRole
    exp: datetime


class PasswordReset(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str = Field(..., min_length=8)


class UserStats(BaseModel):
    """User statistics and usage data."""
    user_id: str
    total_documents: int
    total_summaries: int
    total_recommendations: int
    storage_used_mb: float
    api_calls_this_month: int
    favorite_topics: List[str]
    recent_activity: List[Dict[str, Any]]
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_documents": 42,
                "total_summaries": 156,
                "total_recommendations": 89,
                "storage_used_mb": 234.5,
                "api_calls_this_month": 450,
                "favorite_topics": ["machine learning", "neuroscience", "AI"],
                "recent_activity": [
                    {
                        "action": "summary_generated",
                        "document_title": "Deep Learning in Healthcare",
                        "timestamp": "2025-07-09T10:30:00Z"
                    }
                ]
            }
        }