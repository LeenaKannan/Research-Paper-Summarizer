# backend/database/operations.py
"""
Database CRUD operations for all models.
Provides async functions for interacting with MongoDB collections.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from .connection import db_manager
from ..models.user import UserInDB, UserCreate, UserUpdate
from ..models.document import DocumentInDB, DocumentCreate, DocumentUpdate, DocumentStatus
from ..models.summary import SummaryInDB, SummaryCreate, SummaryUpdate

logger = logging.getLogger(__name__)


# Utility functions
def to_object_id(id_str: str) -> ObjectId:
    """Convert string ID to MongoDB ObjectId."""
    try:
        return ObjectId(id_str)
    except:
        raise ValueError(f"Invalid ID format: {id_str}")


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize MongoDB document for API response."""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


# User operations
class UserOperations:
    """Database operations for users."""
    
    @staticmethod
    async def create_user(user_data: UserCreate, hashed_password: str) -> UserInDB:
        """Create a new user in the database."""
        user_dict = user_data.dict()
        user_dict.pop("password")
        
        user_db = UserInDB(
            **user_dict,
            hashed_password=hashed_password,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await db_manager.users_collection.insert_one(user_db.dict())
        user_db.id = str(result.inserted_id)
        
        logger.info(f"Created user: {user_db.username}")
        return user_db
    
    @staticmethod
    async def get_user(user_id: str) -> Optional[UserInDB]:
        """Get user by ID."""
        doc = await db_manager.users_collection.find_one({"_id": to_object_id(user_id)})
        if doc:
            return UserInDB(**serialize_doc(doc))
        return None
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[UserInDB]:
        """Get user by email."""
        doc = await db_manager.users_collection.find_one({"email": email})
        if doc:
            return UserInDB(**serialize_doc(doc))
        return None
    
    @staticmethod
    async def get_user_by_username(username: str) -> Optional[UserInDB]:
        """Get user by username."""
        doc = await db_manager.users_collection.find_one({"username": username})
        if doc:
            return UserInDB(**serialize_doc(doc))
        return None
    
    @staticmethod
    async def update_user(user_id: str, user_update: UserUpdate) -> Optional[UserInDB]:
        """Update user information."""
        update_data = user_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db_manager.users_collection.find_one_and_update(
            {"_id": to_object_id(user_id)},
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            return UserInDB(**serialize_doc(result))
        return None
    
    @staticmethod
    async def update_last_login(user_id: str) -> None:
        """Update user's last login timestamp."""
        await db_manager.users_collection.update_one(
            {"_id": to_object_id(user_id)},
            {"$set": {"last_login": datetime.utcnow()}}
        )
    
    @staticmethod
    async def increment_user_stats(user_id: str, field: str, amount: int = 1) -> None:
        """Increment user statistics counters."""
        await db_manager.users_collection.update_one(
            {"_id": to_object_id(user_id)},
            {"$inc": {field: amount}}
        )
    
    @staticmethod
    async def delete_user(user_id: str) -> bool:
        """Soft delete a user (marks as inactive)."""
        result = await db_manager.users_collection.update_one(
            {"_id": to_object_id(user_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0


# Document operations
class DocumentOperations:
    """Database operations for documents."""
    
    @staticmethod
    async def create_document(doc_data: DocumentCreate) -> DocumentInDB:
        """Create a new document in the database."""
        doc_db = DocumentInDB(**doc_data.dict())
        
        result = await db_manager.documents_collection.insert_one(doc_db.dict())
        doc_db.id = str(result.inserted_id)
        
        # Update user stats
        await UserOperations.increment_user_stats(doc_data.user_id, "documents_uploaded")
        
        logger.info(f"Created document: {doc_db.filename}")
        return doc_db
    
    @staticmethod
    async def get_document(document_id: str) -> Optional[DocumentInDB]:
        """Get document by ID."""
        doc = await db_manager.documents_collection.find_one({"_id": to_object_id(document_id)})
        if doc:
            # Update last accessed
            await db_manager.documents_collection.update_one(
                {"_id": to_object_id(document_id)},
                {"$set": {"last_accessed": datetime.utcnow()}}
            )
            return DocumentInDB(**serialize_doc(doc))
        return None
    
    @staticmethod
    async def get_user_documents(
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[DocumentStatus] = None
    ) -> Dict[str, Any]:
        """Get documents for a user with pagination."""
        query = {"user_id": user_id}
        if status:
            query["status"] = status.value
        
        # Count total documents
        total = await db_manager.documents_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = db_manager.documents_collection.find(query).skip(skip).limit(page_size).sort("upload_date", -1)
        
        documents = []
        async for doc in cursor:
            documents.append(DocumentInDB(**serialize_doc(doc)))
        
        return {
            "documents": documents,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    @staticmethod
    async def update_document(document_id: str, update_data: DocumentUpdate) -> Optional[DocumentInDB]:
        """Update document information."""
        update_dict = update_data.dict(exclude_unset=True)
        
        if "status" in update_dict and update_dict["status"] == DocumentStatus.READY:
            update_dict["processed_date"] = datetime.utcnow()
        
        result = await db_manager.documents_collection.find_one_and_update(
            {"_id": to_object_id(document_id)},
            {"$set": update_dict},
            return_document=True
        )
        
        if result:
            return DocumentInDB(**serialize_doc(result))
        return None
    
    @staticmethod
    async def search_documents(
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[DocumentInDB]:
        """Search documents using text search."""
        search_query = {
            "user_id": user_id,
            "$text": {"$search": query}
        }
        
        cursor = db_manager.documents_collection.find(
            search_query,
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        documents = []
        async for doc in cursor:
            documents.append(DocumentInDB(**serialize_doc(doc)))
        
        return documents
    
    @staticmethod
    async def delete_document(document_id: str) -> bool:
        """Soft delete a document."""
        result = await db_manager.documents_collection.update_one(
            {"_id": to_object_id(document_id)},
            {"$set": {"status": DocumentStatus.DELETED.value}}
        )
        return result.modified_count > 0


# Summary operations
class SummaryOperations:
    """Database operations for summaries."""
    
    @staticmethod
    async def create_summary(summary_data: SummaryCreate, content: Dict[str, Any], generation_metadata: Dict[str, Any]) -> SummaryInDB:
        """Create a new summary in the database."""
        summary_db = SummaryInDB(
            **summary_data.dict(),
            content=content,
            **generation_metadata
        )
        
        result = await db_manager.summaries_collection.insert_one(summary_db.dict())
        summary_db.id = str(result.inserted_id)
        
        # Update user stats
        await UserOperations.increment_user_stats(summary_data.user_id, "summaries_generated")
        
        logger.info(f"Created summary for document: {summary_db.document_id}")
        return summary_db
    
    @staticmethod
    async def get_summary(summary_id: str) -> Optional[SummaryInDB]:
        """Get summary by ID."""
        doc = await db_manager.summaries_collection.find_one({"_id": to_object_id(summary_id)})
        if doc:
            # Update view count and last viewed
            await db_manager.summaries_collection.update_one(
                {"_id": to_object_id(summary_id)},
                {
                    "$inc": {"view_count": 1},
                    "$set": {"last_viewed": datetime.utcnow()}
                }
            )
            return SummaryInDB(**serialize_doc(doc))
        return None
    
    @staticmethod
    async def get_document_summaries(document_id: str) -> List[SummaryInDB]:
        """Get all summaries for a document."""
        cursor = db_manager.summaries_collection.find(
            {"document_id": document_id}
        ).sort("created_at", -1)
        
        summaries = []
        async for doc in cursor:
            summaries.append(SummaryInDB(**serialize_doc(doc)))
        
        return summaries
    
    @staticmethod
    async def get_user_summaries(
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get summaries for a user with pagination."""
        query = {"user_id": user_id}
        
        # Count total
        total = await db_manager.summaries_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = db_manager.summaries_collection.find(query).skip(skip).limit(page_size).sort("created_at", -1)
        
        summaries = []
        async for doc in cursor:
            summaries.append(SummaryInDB(**serialize_doc(doc)))
        
        return {
            "summaries": summaries,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    @staticmethod
    async def update_summary(summary_id: str, update_data: SummaryUpdate) -> Optional[SummaryInDB]:
        """Update summary information."""
        update_dict = update_data.dict(exclude_unset=True)
        
        result = await db_manager.summaries_collection.find_one_and_update(
            {"_id": to_object_id(summary_id)},
            {"$set": update_dict},
            return_document=True
        )
        
        if result:
            return SummaryInDB(**serialize_doc(result))
        return None
    
    @staticmethod
    async def get_summary_analytics(user_id: str) -> Dict[str, Any]:
        """Get summary analytics for a user."""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "total_summaries": {"$sum": 1},
                    "average_rating": {"$avg": "$rating"},
                    "total_views": {"$sum": "$view_count"},
                    "total_exports": {"$sum": "$exported_count"}
                }
            }
        ]
        
        cursor = db_manager.summaries_collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if result:
            return result[0]
        return {
            "total_summaries": 0,
            "average_rating": 0,
            "total_views": 0,
            "total_exports": 0
        }


# Session operations
class SessionOperations:
    """Database operations for user sessions."""
    
    @staticmethod
    async def create_session(user_id: str, token: str, expires_delta: timedelta) -> str:
        """Create a new session."""
        session_data = {
            "user_id": user_id,
            "token": token,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + expires_delta,
            "is_active": True
        }
        
        result = await db_manager.sessions_collection.insert_one(session_data)
        return str(result.inserted_id)
    
    @staticmethod
    async def get_session(token: str) -> Optional[Dict[str, Any]]:
        """Get active session by token."""
        session = await db_manager.sessions_collection.find_one({
            "token": token,
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if session:
            return serialize_doc(session)
        return None
    
    @staticmethod
    async def invalidate_session(token: str) -> bool:
        """Invalidate a session."""
        result = await db_manager.sessions_collection.update_one(
            {"token": token},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0
    
    @staticmethod
    async def cleanup_expired_sessions() -> int:
        """Remove expired sessions."""
        result = await db_manager.sessions_collection.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })
        return result.deleted_count