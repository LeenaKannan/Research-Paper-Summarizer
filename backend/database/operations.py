from typing import Optional, List, Dict, Any, Union
from bson import ObjectId
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError
import logging
from .database import db_manager
from models.schemas import UserSchema, DocumentSchema, SummarySchema, RecommendationSchema, SessionSchema

logger = logging.getLogger(__name__)

class CRUDOperations:
    def __init__(self):
        self.db = db_manager

    # User CRUD Operations
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """Create a new user"""
        try:
            user = UserSchema(**user_data)
            result = await self.db.get_collection('users').insert_one(user.dict(by_alias=True))
            logger.info(f"User created with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            logger.error(f"User already exists: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            user = await self.db.get_collection('users').find_one({"_id": ObjectId(user_id)})
            return user
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            user = await self.db.get_collection('users').find_one({"username": username})
            return user
        except Exception as e:
            logger.error(f"Error fetching user by username: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            user = await self.db.get_collection('users').find_one({"email": email})
            return user
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update user information"""
        try:
            result = await self.db.get_collection('users').update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False

    async def update_user_login(self, user_id: str) -> bool:
        """Update user's last login time"""
        try:
            result = await self.db.get_collection('users').update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user login: {e}")
            return False

    # Document CRUD Operations
    async def create_document(self, document_data: Dict[str, Any]) -> Optional[str]:
        """Create a new document"""
        try:
            document = DocumentSchema(**document_data)
            result = await self.db.get_collection('documents').insert_one(document.dict(by_alias=True))
            logger.info(f"Document created with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating document: {e}")
            return None

    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            document = await self.db.get_collection('documents').find_one({"_id": ObjectId(document_id)})
            return document
        except Exception as e:
            logger.error(f"Error fetching document: {e}")
            return None

    async def get_user_documents(self, user_id: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get documents for a specific user"""
        try:
            cursor = self.db.get_collection('documents').find(
                {"user_id": ObjectId(user_id)}
            ).sort("upload_date", -1).skip(skip).limit(limit)
            
            documents = await cursor.to_list(length=limit)
            return documents
        except Exception as e:
            logger.error(f"Error fetching user documents: {e}")
            return []

    async def update_document_status(self, document_id: str, status: str) -> bool:
        """Update document processing status"""
        try:
            result = await self.db.get_collection('documents').update_one(
                {"_id": ObjectId(document_id)},
                {"$set": {"processing_status": status}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating document status: {e}")
            return False

    async def search_documents(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search documents by text"""
        try:
            cursor = self.db.get_collection('documents').find(
                {
                    "user_id": ObjectId(user_id),
                    "$text": {"$search": query}
                },
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            documents = await cursor.to_list(length=limit)
            return documents
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

    # Summary CRUD Operations
    async def create_summary(self, summary_data: Dict[str, Any]) -> Optional[str]:
        """Create a new summary"""
        try:
            summary = SummarySchema(**summary_data)
            result = await self.db.get_collection('summaries').insert_one(summary.dict(by_alias=True))
            logger.info(f"Summary created with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return None

    async def get_document_summaries(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all summaries for a document"""
        try:
            cursor = self.db.get_collection('summaries').find(
                {"document_id": ObjectId(document_id)}
            ).sort("created_at", -1)
            
            summaries = await cursor.to_list(length=None)
            return summaries
        except Exception as e:
            logger.error(f"Error fetching document summaries: {e}")
            return []

    async def get_user_summaries(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent summaries for a user"""
        try:
            cursor = self.db.get_collection('summaries').find(
                {"user_id": ObjectId(user_id)}
            ).sort("created_at", -1).limit(limit)
            
            summaries = await cursor.to_list(length=limit)
            return summaries
        except Exception as e:
            logger.error(f"Error fetching user summaries: {e}")
            return []

    # Recommendation CRUD Operations
    async def create_recommendations(self, recommendations_data: List[Dict[str, Any]]) -> List[str]:
        """Create multiple recommendations"""
        try:
            recommendations = [RecommendationSchema(**data) for data in recommendations_data]
            docs = [rec.dict(by_alias=True) for rec in recommendations]
            
            result = await self.db.get_collection('recommendations').insert_many(docs)
            logger.info(f"Created {len(result.inserted_ids)} recommendations")
            return [str(id) for id in result.inserted_ids]
        except Exception as e:
            logger.error(f"Error creating recommendations: {e}")
            return []

    async def get_document_recommendations(self, document_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recommendations for a document"""
        try:
            cursor = self.db.get_collection('recommendations').find(
                {"document_id": ObjectId(document_id)}
            ).sort("similarity_score", -1).limit(limit)
            
            recommendations = await cursor.to_list(length=limit)
            return recommendations
        except Exception as e:
            logger.error(f"Error fetching recommendations: {e}")
            return []

    async def update_recommendation_feedback(self, recommendation_id: str, is_relevant: bool) -> bool:
        """Update recommendation relevance feedback"""
        try:
            result = await self.db.get_collection('recommendations').update_one(
                {"_id": ObjectId(recommendation_id)},
                {"$set": {"is_relevant": is_relevant}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating recommendation feedback: {e}")
            return False

    # Session CRUD Operations
    async def create_session(self, session_data: Dict[str, Any]) -> Optional[str]:
        """Create a new session"""
        try:
            session = SessionSchema(**session_data)
            result = await self.db.get_collection('sessions').insert_one(session.dict(by_alias=True))
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None

    async def get_session_by_token(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get session by token"""
        try:
            session = await self.db.get_collection('sessions').find_one({
                "session_token": session_token,
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            return session
        except Exception as e:
            logger.error(f"Error fetching session: {e}")
            return None

    async def invalidate_session(self, session_token: str) -> bool:
        """Invalidate a session"""
        try:
            result = await self.db.get_collection('sessions').update_one(
                {"session_token": session_token},
                {"$set": {"is_active": False}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error invalidating session: {e}")
            return False

    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        try:
            result = await self.db.get_collection('sessions').delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            logger.info(f"Cleaned up {result.deleted_count} expired sessions")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0

    # Analytics and Statistics
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            pipeline = [
                {"$match": {"user_id": ObjectId(user_id)}},
                {"$group": {
                    "_id": None,
                    "total_documents": {"$sum": 1},
                    "total_size": {"$sum": "$file_size"},
                    "avg_size": {"$avg": "$file_size"}
                }}
            ]
            
            result = await self.db.get_collection('documents').aggregate(pipeline).to_list(1)
            
            if result:
                stats = result[0]
                del stats["_id"]
            else:
                stats = {"total_documents": 0, "total_size": 0, "avg_size": 0}
            
            # Get summary count
            summary_count = await self.db.get_collection('summaries').count_documents(
                {"user_id": ObjectId(user_id)}
            )
            stats["total_summaries"] = summary_count
            
            return stats
        except Exception as e:
            logger.error(f"Error fetching user stats: {e}")
            return {}

# Global CRUD operations instance
crud = CRUDOperations()
