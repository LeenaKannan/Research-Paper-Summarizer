# backend/database/connection.py
"""
MongoDB connection manager.
Handles database connections and provides database instances.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure
from typing import Optional
import logging
from contextlib import asynccontextmanager

from ..config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB connections and database operations."""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self) -> None:
        """
        Establish connection to MongoDB.
        Raises ConnectionFailure if unable to connect.
        """
        try:
            self.client = AsyncIOMotorClient(
                settings.mongodb_url,
                maxPoolSize=10,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000
            )
            
            # Verify connection
            await self.client.admin.command('ping')
            
            self.database = self.client[settings.mongodb_name]
            logger.info(f"Connected to MongoDB: {settings.mongodb_name}")
            
            # Create indexes
            await self._create_indexes()
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def _create_indexes(self) -> None:
        """Create database indexes for better performance."""
        try:
            # User indexes
            await self.database.users.create_index("email", unique=True)
            await self.database.users.create_index("username", unique=True)
            
            # Document indexes
            await self.database.documents.create_index("user_id")
            await self.database.documents.create_index("upload_date")
            await self.database.documents.create_index([("title", "text"), ("content", "text")])
            
            # Summary indexes
            await self.database.summaries.create_index("document_id")
            await self.database.summaries.create_index("user_id")
            await self.database.summaries.create_index("created_at")
            
            # Session indexes
            await self.database.sessions.create_index("user_id")
            await self.database.sessions.create_index("expires_at", expireAfterSeconds=0)
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise
    
    def get_collection(self, collection_name: str):
        """Get a specific collection from the database."""
        if not self.database:
            raise RuntimeError("Database not connected")
        return self.database[collection_name]
    
    @property
    def users_collection(self):
        """Get users collection."""
        return self.get_collection("users")
    
    @property
    def documents_collection(self):
        """Get documents collection."""
        return self.get_collection("documents")
    
    @property
    def summaries_collection(self):
        """Get summaries collection."""
        return self.get_collection("summaries")
    
    @property
    def sessions_collection(self):
        """Get sessions collection."""
        return self.get_collection("sessions")


# Global database manager instance
db_manager = DatabaseManager()


@asynccontextmanager
async def get_database():
    """
    Async context manager for database operations.
    Ensures proper connection handling.
    """
    if not db_manager.database:
        await db_manager.connect()
    
    try:
        yield db_manager
    finally:
        # Connection is kept alive for the application lifetime
        pass


# Helper functions for direct access
async def get_users_collection():
    """Get users collection directly."""
    if not db_manager.database:
        await db_manager.connect()
    return db_manager.users_collection


async def get_documents_collection():
    """Get documents collection directly."""
    if not db_manager.database:
        await db_manager.connect()
    return db_manager.documents_collection


async def get_summaries_collection():
    """Get summaries collection directly."""
    if not db_manager.database:
        await db_manager.connect()
    return db_manager.summaries_collection