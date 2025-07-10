import streamlit as st
import asyncio
from typing import Optional, Dict, Any
from utils.auth import auth_manager
from utils.database import db_manager

class StreamlitAuth:
    def __init__(self):
        self.auth = auth_manager
        
    def init_session_state(self):
        """Initialize session state variables"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user_data' not in st.session_state:
            st.session_state.user_data = None
        if 'session_token' not in st.session_state:
            st.session_state.session_token = None

    async def login_form(self) -> bool:
        """Display login form and handle authentication"""
        st.subheader("🔐 Login")
        
        with st.form("login_form"):
            username = st.text_input("Username or Email", placeholder="Enter your username or email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            remember_me = st.checkbox("Remember me")
            
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("Login", use_container_width=True)
            with col2:
                register_button = st.form_submit_button("Register", use_container_width=True)
            
            if login_button:
                if username and password:
                    with st.spinner("Authenticating..."):
                        success, message, user_data = await self.auth.authenticate_user(username, password)
                        
                        if success and user_data:
                            # Create session
                            session_token = await self.auth.create_user_session(
                                user_data['user_id'],
                                ip_address=st.session_state.get('client_ip'),
                                user_agent=st.session_state.get('user_agent')
                            )
                            
                            if session_token:
                                st.session_state.authenticated = True
                                st.session_state.user_data = user_data
                                st.session_state.session_token = session_token
                                st.success(f"Welcome back, {user_data['username']}!")
                                st.rerun()
                            else:
                                st.error("Failed to create session")
                        else:
                            st.error(message)
                else:
                    st.error("Please enter both username and password")
            
            if register_button:
                st.session_state.show_register = True
                st.rerun()
        
        return st.session_state.authenticated

    async def register_form(self) -> bool:
        """Display registration form"""
        st.subheader("📝 Register")
        
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("Username*", placeholder="Choose a username")
                email = st.text_input("Email*", placeholder="Enter your email")
                password = st.text_input("Password*", type="password", placeholder="Create a password")
            
            with col2:
                full_name = st.text_input("Full Name", placeholder="Your full name")
                institution = st.text_input("Institution", placeholder="Your institution/organization")
                confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Confirm your password")
            
            terms_accepted = st.checkbox("I agree to the Terms of Service and Privacy Policy")
            
            col1, col2 = st.columns(2)
            with col1:
                register_button = st.form_submit_button("Create Account", use_container_width=True)
            with col2:
                back_button = st.form_submit_button("Back to Login", use_container_width=True)
            
            if register_button:
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill in all required fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters long")
                elif not terms_accepted:
                    st.error("Please accept the Terms of Service")
                else:
                    with st.spinner("Creating account..."):
                        success, message, user_id = await self.auth.register_user(
                            username, email, password, full_name, institution
                        )
                        
                        if success:
                            st.success("Account created successfully! Please login.")
                            st.session_state.show_register = False
                            st.rerun()
                        else:
                            st.error(message)
            
            if back_button:
                st.session_state.show_register = False
                st.rerun()
        
        return False

    async def validate_session(self) -> bool:
        """Validate current session"""
        if st.session_state.session_token:
            user_data = await self.auth.validate_session(st.session_state.session_token)
            if user_data:
                st.session_state.authenticated = True
                st.session_state.user_data = user_data
                return True
        
        # Clear invalid session
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.session_state.session_token = None
        return False

    async def logout(self):
        """Logout current user"""
        if st.session_state.session_token:
            await self.auth.logout_user(st.session_state.session_token)
        
        # Clear session state
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.session_state.session_token = None
        st.rerun()

    def require_auth(self, func):
        """Decorator to require authentication"""
        async def wrapper(*args, **kwargs):
            if not st.session_state.authenticated:
                if not await self.validate_session():
                    st.warning("Please login to access this page")
                    return await self.login_form()
            return await func(*args, **kwargs)
        return wrapper

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user data"""
        return st.session_state.user_data

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return st.session_state.authenticated

# Global auth instance
streamlit_auth = StreamlitAuth()

# Async wrapper for Streamlit
def run_async(coro):
    """Run async function in Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)
