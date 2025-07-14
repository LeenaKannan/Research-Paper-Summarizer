# backend/models/document.py
"""
Document data models and schemas.
Defines document-related data structures for research papers.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class DocumentType(str, Enum):
    """Document type enumeration."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class DocumentStatus(str, Enum):
    """Document processing status."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class DocumentSection(BaseModel):
    """Represents a section within a document."""
    title: str
    content: str
    page_numbers: List[int] = []
    word_count: int = 0
    
    @validator('word_count', always=True)
    def calculate_word_count(cls, v, values):
        """Calculate word count if not provided."""
        if v == 0 and 'content' in values:
            return len(values['content'].split())
        return v


class DocumentMetadata(BaseModel):
    """Document metadata extracted during processing."""
    title: Optional[str] = None
    authors: List[str] = []
    abstract: Optional[str] = None
    keywords: List[str] = []
    publication_date: Optional[datetime] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    citations_count: Optional[int] = None
    
    # Extracted sections
    sections: List[DocumentSection] = []
    
    # Document statistics
    total_pages: Optional[int] = None
    total_words: Optional[int] = None
    language: str = "en"
    
    # AI-extracted features
    main_topics: List[str] = []
    methodology: Optional[str] = None
    key_findings: List[str] = []


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str
    file_type: DocumentType
    file_size: int  # in bytes
    content_hash: str  # SHA-256 hash of file content
    
    @validator('file_size')
    def validate_file_size(cls, v):
        """Ensure file size is within limits."""
        max_size = 10 * 1024 * 1024  # 10MB
        if v > max_size:
            raise ValueError(f'File size exceeds maximum allowed size of {max_size} bytes')
        return v


class DocumentCreate(DocumentBase):
    """Schema for creating a new document."""
    user_id: str
    content: Optional[str] = None  # Raw text content
    file_path: Optional[str] = None  # Path to uploaded file


class DocumentUpdate(BaseModel):
    """Schema for updating document information."""
    metadata: Optional[DocumentMetadata] = None
    status: Optional[DocumentStatus] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class DocumentInDB(DocumentBase):
    """Document schema as stored in database."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    
    # File information
    file_path: str  # Path to stored file
    original_filename: str
    
    # Content
    content: Optional[str] = None  # Extracted text content
    content_embedding: Optional[List[float]] = None  # Vector embedding
    
    # Metadata
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    
    # Status and timestamps
    status: DocumentStatus = DocumentStatus.UPLOADING
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    processed_date: Optional[datetime] = None
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    
    # User annotations
    tags: List[str] = []
    notes: Optional[str] = None
    is_favorite: bool = False
    
    # Processing information
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    
    # Related documents
    similar_documents: List[Dict[str, Any]] = []  # List of {document_id, similarity_score}
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DocumentResponse(BaseModel):
    """Document schema for API responses."""
    id: str
    filename: str
    original_filename: str
    file_type: DocumentType
    file_size: int
    status: DocumentStatus
    upload_date: datetime
    processed_date: Optional[datetime]
    metadata: DocumentMetadata
    tags: List[str]
    notes: Optional[str]
    is_favorite: bool
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DocumentListResponse(BaseModel):
    """Response schema for document list endpoints."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    
    class Config:
        schema_extra = {
            "example": {
                "documents": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "filename": "deep_learning_healthcare.pdf",
                        "file_type": "pdf",
                        "status": "ready",
                        "upload_date": "2025-07-09T10:30:00Z"
                    }
                ],
                "total": 42,
                "page": 1,
                "page_size": 10
            }
        }


class DocumentSearchQuery(BaseModel):
    """Search query for documents."""
    query: str
    filters: Optional[Dict[str, Any]] = None
    sort_by: str = "relevance"  # relevance, date, title
    page: int = 1
    page_size: int = 10
    
    @validator('page')
    def validate_page(cls, v):
        if v < 1:
            raise ValueError('Page must be >= 1')
        return v
    
    @validator('page_size')
    def validate_page_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError('Page size must be between 1 and 100')
        return v


class SimilarDocumentRequest(BaseModel):
    """Request schema for finding similar documents."""
    document_id: str
    top_k: int = 5
    min_similarity: float = 0.7
    
    @validator('top_k')
    def validate_top_k(cls, v):
        if v < 1 or v > 20:
            raise ValueError('top_k must be between 1 and 20')
        return v
    
    @validator('min_similarity')
    def validate_similarity(cls, v):
        if v < 0 or v > 1:
            raise ValueError('min_similarity must be between 0 and 1')
        return v


class DocumentAnalytics(BaseModel):
    """Document analytics and insights."""
    document_id: str
    reading_time_minutes: int
    complexity_score: float  # 0-1, higher is more complex
    readability_score: float  # Flesch reading ease
    topic_distribution: Dict[str, float]
    citation_network: List[Dict[str, Any]]
    key_concepts: List[str]
    summary_views: int
    download_count: int