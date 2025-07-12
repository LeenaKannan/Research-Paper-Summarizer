# backend/routers/auth.py
"""
Authentication router.
Handles user registration, login, logout, and token management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
import logging

from ..models.user import (
    UserCreate, UserResponse, UserLogin, Token,
    PasswordReset, PasswordResetConfirm
)
from ..services.user_service import user_service
from ..services.email_service import email_service  # You'll need to create this

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current authenticated user."""
    user = await user_service.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Register a new user.
    
    - **email**: User's email address (must be unique)
    - **username**: Username (must be unique, 3-50 characters)
    - **password**: Password (min 8 chars, must contain uppercase, lowercase, and digit)
    - **full_name**: Optional full name
    """
    try:
        user = await user_service.register_user(user_data)
        
        # Send welcome email (optional)
        # await email_service.send_welcome_email(user.email, user.username)
        
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            role=user.role,
            preferences=user.preferences,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
            email_verified=user.email_verified,
            documents_uploaded=user.documents_uploaded,
            summaries_generated=user.summaries_generated,
            subscription_tier=user.subscription_tier
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login with username/email and password.
    
    Returns access and refresh tokens.
    """
    user = await user_service.authenticate_user(
        form_data.username,  # Can be username or email
        form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    # Create tokens
    tokens = await user_service.create_tokens(user)
    
    logger.info(f"User logged in: {user.username}")
    
    return tokens


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token.
    """
    tokens = await user_service.refresh_access_token(refresh_token)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(oauth2_scheme),
    user=Depends(get_current_user)
):
    """
    Logout current user by invalidating their session.
    """
    success = await user_service.logout_user(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )
    
    logger.info(f"User logged out: {user.username}")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user=Depends(get_current_user)):
    """
    Get current user information.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        role=user.role,
        preferences=user.preferences,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        email_verified=user.email_verified,
        documents_uploaded=user.documents_uploaded,
        summaries_generated=user.summaries_generated,
        subscription_tier=user.subscription_tier
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    old_password: str,
    new_password: str,
    user=Depends(get_current_user)
):
    """
    Change password for current user.
    """
    success = await user_service.change_password(
        user.id,
        old_password,
        new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password"
        )
    
    logger.info(f"Password changed for user: {user.username}")


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(data: PasswordReset):
    """
    Request password reset email.
    """
    user = await user_service.get_user_by_email(data.email)
    
    # Don't reveal if email exists or not for security
    if user:
        reset_token = user_service.generate_password_reset_token(data.email)
        
        # Send reset email
        # await email_service.send_password_reset_email(
        #     data.email,
        #     reset_token
        # )
        
        logger.info(f"Password reset requested for: {data.email}")


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: PasswordResetConfirm):
    """
    Reset password using reset token.
    """
    success = await user_service.reset_password(
        data.token,
        data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    logger.info("Password reset successful")


@router.get("/verify-email/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(token: str):
    """
    Verify email address using verification token.
    """
    # Implementation depends on your email verification strategy
    # This is a placeholder
    pass


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification_email(user=Depends(get_current_user)):
    """
    Resend email verification link.
    """
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Send verification email
    # verification_token = user_service.generate_email_verification_token(user.email)
    # await email_service.send_verification_email(user.email, verification_token)
    
    logger.info(f"Verification email resent to: {user.email}")


# OAuth2 endpoints (optional, for third-party authentication)
@router.get("/oauth/{provider}")
async def oauth_login(provider: str, request: Request):
    """
    Initiate OAuth login flow.
    
    Supported providers: google, github
    """
    # Implement OAuth flow
    pass


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str):
    """
    OAuth callback endpoint.
    """
    # Handle OAuth callback
    pass