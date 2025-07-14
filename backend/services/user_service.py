# backend/services/user_service.py
"""
User service for authentication and user management.
Handles user registration, login, and JWT tokens.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import string

from ..config.settings import settings
from ..models.user import UserCreate, UserInDB, UserUpdate, Token, TokenData
from ..database.operations import UserOperations, SessionOperations

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """Service for user authentication and management."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days
    
    # Password handling
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    # Token handling
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        return encoded_jwt
    
    async def create_tokens(self, user: UserInDB) -> Token:
        """Create both access and refresh tokens for a user."""
        token_data = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token(token_data)
        
        # Store refresh token in database
        await SessionOperations.create_session(
            user_id=user.id,
            token=refresh_token,
            expires_delta=timedelta(days=self.refresh_token_expire_days)
        )
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60  # in seconds
        )
    
    async def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenData]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != token_type:
                return None
            
            # Check if it's a refresh token and if it's still valid in DB
            if token_type == "refresh":
                session = await SessionOperations.get_session(token)
                if not session:
                    return None
            
            return TokenData(
                user_id=payload.get("user_id"),
                username=payload.get("username"),
                email=payload.get("email"),
                role=payload.get("role"),
                exp=datetime.fromtimestamp(payload.get("exp"))
            )
            
        except JWTError as e:
            logger.error(f"Token verification failed: {e}")
            return None
    
    # User management
    async def register_user(self, user_data: UserCreate) -> UserInDB:
        """Register a new user."""
        # Check if user already exists
        existing_user = await UserOperations.get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("Email already registered")
        
        existing_user = await UserOperations.get_user_by_username(user_data.username)
        if existing_user:
            raise ValueError("Username already taken")
        
        # Hash password
        hashed_password = self.get_password_hash(user_data.password)
        
        # Create user
        user = await UserOperations.create_user(user_data, hashed_password)
        
        logger.info(f"User registered: {user.username}")
        return user
    
    async def authenticate_user(self, username_or_email: str, password: str) -> Optional[UserInDB]:
        """Authenticate a user by username/email and password."""
        # Try to find user by email first
        user = await UserOperations.get_user_by_email(username_or_email)
        
        # If not found, try username
        if not user:
            user = await UserOperations.get_user_by_username(username_or_email)
        
        if not user:
            return None
        
        if not self.verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        await UserOperations.update_last_login(user.id)
        
        return user
    
    async def get_current_user(self, token: str) -> Optional[UserInDB]:
        """Get current user from token."""
        token_data = await self.verify_token(token)
        if not token_data:
            return None
        
        user = await UserOperations.get_user(token_data.user_id)
        
        if not user or not user.is_active:
            return None
        
        return user
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[Token]:
        """Refresh access token using refresh token."""
        token_data = await self.verify_token(refresh_token, token_type="refresh")
        if not token_data:
            return None
        
        user = await UserOperations.get_user(token_data.user_id)
        if not user or not user.is_active:
            return None
        
        # Create new tokens
        return await self.create_tokens(user)
    
    async def logout_user(self, token: str) -> bool:
        """Logout user by invalidating their session."""
        return await SessionOperations.invalidate_session(token)
    
    async def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[UserInDB]:
        """Update user information."""
        # If password is being updated, hash it
        if user_update.password:
            user_update.password = self.get_password_hash(user_update.password)
        
        return await UserOperations.update_user(user_id, user_update)
    
    async def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password."""
        user = await UserOperations.get_user(user_id)
        if not user:
            return False
        
        # Verify old password
        if not self.verify_password(old_password, user.hashed_password):
            return False
        
        # Update password
        hashed_password = self.get_password_hash(new_password)
        update_data = UserUpdate(password=hashed_password)
        
        updated_user = await UserOperations.update_user(user_id, update_data)
        return updated_user is not None
    
    def generate_password_reset_token(self, email: str) -> str:
        """Generate a password reset token."""
        data = {
            "email": email,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        
        return jwt.encode(data, self.secret_key, algorithm=self.algorithm)
    
    async def verify_password_reset_token(self, token: str) -> Optional[str]:
        """Verify password reset token and return email."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("type") != "password_reset":
                return None
            
            return payload.get("email")
            
        except JWTError:
            return None
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset user password using reset token."""
        email = await self.verify_password_reset_token(token)
        if not email:
            return False
        
        user = await UserOperations.get_user_by_email(email)
        if not user:
            return False
        
        # Update password
        hashed_password = self.get_password_hash(new_password)
        update_data = UserUpdate(password=hashed_password)
        
        updated_user = await UserOperations.update_user(user.id, update_data)
        return updated_user is not None
    
    def generate_api_key(self) -> str:
        """Generate a secure API key."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    async def verify_api_key(self, api_key: str) -> Optional[UserInDB]:
        """Verify API key and return associated user."""
        # In a real implementation, store API keys in database
        # This is a simplified version
        # You would query the database for the API key and return the associated user
        pass
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics."""
        user = await UserOperations.get_user(user_id)
        if not user:
            return {}
        
        return {
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "documents_uploaded": user.documents_uploaded,
            "summaries_generated": user.summaries_generated,
            "storage_used_mb": user.storage_used_mb,
            "api_calls_count": user.api_calls_count,
            "subscription_tier": user.subscription_tier,
            "member_since": user.created_at.isoformat(),
            "last_active": user.last_login.isoformat() if user.last_login else None
        }


# Singleton instance
user_service = UserService()