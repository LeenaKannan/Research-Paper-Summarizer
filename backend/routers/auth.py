import os
import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import logging
from .crud_operations import crud

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        self.expiration_hours = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
        
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY environment variable is required")

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

    def generate_jwt_token(self, user_id: str, username: str) -> str:
        """Generate JWT token for user"""
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=self.expiration_hours),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
            return None

    def generate_session_token(self) -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)

    async def register_user(self, username: str, email: str, password: str, 
                          full_name: Optional[str] = None, 
                          institution: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """Register a new user"""
        try:
            # Check if user already exists
            existing_user = await crud.get_user_by_username(username)
            if existing_user:
                return False, "Username already exists", None
            
            existing_email = await crud.get_user_by_email(email)
            if existing_email:
                return False, "Email already registered", None
            
            # Hash password
            password_hash = self.hash_password(password)
            
            # Create user data
            user_data = {
                'username': username,
                'email': email,
                'password_hash': password_hash,
                'full_name': full_name,
                'institution': institution,
                'created_at': datetime.utcnow(),
                'is_active': True,
                'upload_count': 0,
                'storage_used': 0
            }
            
            # Create user
            user_id = await crud.create_user(user_data)
            if user_id:
                logger.info(f"User registered successfully: {username}")
                return True, "User registered successfully", user_id
            else:
                return False, "Failed to create user", None
                
        except Exception as e:
            logger.error(f"Error during user registration: {e}")
            return False, f"Registration failed: {str(e)}", None

    async def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Authenticate user login"""
        try:
            # Get user by username or email
            user = await crud.get_user_by_username(username)
            if not user:
                user = await crud.get_user_by_email(username)
            
            if not user:
                return False, "User not found", None
            
            if not user.get('is_active', True):
                return False, "Account is deactivated", None
            
            # Verify password
            if not self.verify_password(password, user['password_hash']):
                return False, "Invalid password", None
            
            # Update last login
            await crud.update_user_login(str(user['_id']))
            
            # Remove sensitive data
            user_data = {
                'user_id': str(user['_id']),
                'username': user['username'],
                'email': user['email'],
                'full_name': user.get('full_name'),
                'institution': user.get('institution'),
                'preferences': user.get('preferences', {}),
                'last_login': user.get('last_login')
            }
            
            logger.info(f"User authenticated successfully: {username}")
            return True, "Authentication successful", user_data
            
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False, f"Authentication failed: {str(e)}", None

    async def create_user_session(self, user_id: str, ip_address: Optional[str] = None, 
                                user_agent: Optional[str] = None) -> Optional[str]:
        """Create a new user session"""
        try:
            session_token = self.generate_session_token()
            expires_at = datetime.utcnow() + timedelta(hours=self.expiration_hours)
            
            session_data = {
                'user_id': user_id,
                'session_token': session_token,
                'expires_at': expires_at,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'is_active': True
            }
            
            session_id = await crud.create_session(session_data)
            if session_id:
                return session_token
            return None
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None

    async def validate_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Validate user session"""
        try:
            session = await crud.get_session_by_token(session_token)
            if session:
                # Get user data
                user = await crud.get_user_by_id(str(session['user_id']))
                if user and user.get('is_active', True):
                    return {
                        'user_id': str(user['_id']),
                        'username': user['username'],
                        'email': user['email'],
                        'session_id': str(session['_id'])
                    }
            return None
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return None

    async def logout_user(self, session_token: str) -> bool:
        """Logout user by invalidating session"""
        try:
            return await crud.invalidate_session(session_token)
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return False

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password"""
        try:
            # Get user
            user = await crud.get_user_by_id(user_id)
            if not user:
                return False, "User not found"
            
            # Verify old password
            if not self.verify_password(old_password, user['password_hash']):
                return False, "Current password is incorrect"
            
            # Hash new password
            new_password_hash = self.hash_password(new_password)
            
            # Update password
            success = await crud.update_user(user_id, {'password_hash': new_password_hash})
            if success:
                logger.info(f"Password changed for user: {user['username']}")
                return True, "Password changed successfully"
            else:
                return False, "Failed to update password"
                
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return False, f"Password change failed: {str(e)}"

    async def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """Update user preferences"""
        try:
            return await crud.update_user(user_id, {'preferences': preferences})
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return False

# Global auth manager instance
auth_manager = AuthManager()
