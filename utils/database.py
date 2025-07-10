import os
import logging
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from bson import ObjectId
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _client: Optional[AsyncIOMotorClient] = None
    _database: Optional[AsyncIOMotorDatabase] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """Initialize database connection"""
        if self._client is None:
            try:
                mongodb_uri = os.getenv('MONGODB_URI')
                if not mongodb_uri:
                    raise ValueError("MONGODB_URI environment variable is required")
                
                self._client = AsyncIOMotorClient(mongodb_uri)
                
                # Test connection
                await self._client.admin.command('ping')
                logger.info("Successfully connected to MongoDB Atlas")
                
                db_name = os.getenv('MONGODB_DB_NAME', 'research_summarizer')
                self._database = self._client[db_name]
                
                # Create indexes
                await self._create_indexes()
                
            except ConnectionFailure as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise

    async def disconnect(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("Disconnected from MongoDB")

    async def _create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Users collection indexes
            await self._database.users.create_index("username", unique=True)
            await self._database.users.create_index("email", unique=True)
            await self._database.users.create_index("created_at")
            
            # Documents collection indexes
            await self._database.documents.create_index("user_id")
            await self._database.documents.create_index("upload_date")
            await self._database.documents.create_index("processing_status")
            await self._database.documents.create_index([("title", "text"), ("content_text", "text")])
            
            # Summaries collection indexes
            await self._database.summaries.create_index("document_id")
            await self._database.summaries.create_index("user_id")
            await self._database.summaries.create_index("created_at")
            
            # Recommendations collection indexes
            await self._database.recommendations.create_index("document_id")
            await self._database.recommendations.create_index("user_id")
            await self._database.recommendations.create_index("similarity_score")
            
            # Sessions collection indexes
            await self._database.sessions.create_index("user_id")
            await self._database.sessions.create_index("session_token", unique=True)
            await self._database.sessions.create_index("expires_at", expireAfterSeconds=0)
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    @property
    def database(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._database

    def get_collection(self, collection_name: str):
        return self.database[collection_name]

# Global database manager instance
db_manager = DatabaseManager()
