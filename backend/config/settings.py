# backend/config/settings.py
"""
Application configuration and environment settings.
Handles all environment variables and configuration parameters.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application Settings
    app_name: str = "AI Research Paper Summarizer"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API Settings
    api_v1_prefix: str = "/api/v1"
    
    # MongoDB Settings
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_name: str = "research-summary"
    
    # Authentication Settings
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # OpenAI Settings
    openai_api_key: str = "" #get from .env
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000
    openai_temperature: float = 0.7
    
    # File Upload Settings
    max_upload_size: int = 200 * 1024 * 1024  # 200MB
    allowed_extensions: set = {".pdf", ".docx", ".txt"}
    upload_folder: str = "uploads"
    
    # CORS Settings
    backend_cors_origins: list = ["http://localhost:8501"]  # Streamlit default
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600  # 1 hour in seconds
    
    # Semantic Scholar API
    # semantic_scholar_api_key: Optional[str] = None
    
    # Redis Settings (for caching)
    redis_url: Optional[str] = "redis://localhost:6379"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings():
    """
    Create and cache settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Create settings instance
settings = get_settings()

# Create upload folder if it doesn't exist
os.makedirs(settings.upload_folder, exist_ok=True)