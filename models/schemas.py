from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class UserSchema(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password_hash: str
    full_name: Optional[str] = None
    institution: Optional[str] = None
    research_interests: List[str] = []
    preferences: Dict[str, Any] = {
        "summary_length": "medium",
        "summary_mode": "abstractive",
        "simplify_jargon": False
    }
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    is_active: bool = True
    upload_count: int = 0
    storage_used: int = 0  # in bytes

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class DocumentSchema(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    filename: str
    original_filename: str
    file_type: str  # pdf, docx, txt
    file_size: int  # in bytes
    file_path: str  # storage path
    title: Optional[str] = None
    authors: List[str] = []
    abstract: Optional[str] = None
    keywords: List[str] = []
    publication_date: Optional[datetime] = None
    doi: Optional[str] = None
    content_text: str  # extracted text content
    content_sections: Dict[str, str] = {}  # section_name: content
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    processing_status: str = "pending"  # pending, processing, completed, failed
    metadata: Dict[str, Any] = {}

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class SummarySchema(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    document_id: PyObjectId
    user_id: PyObjectId
    summary_type: str  # full, section, custom
    summary_mode: str  # extractive, abstractive
    summary_length: str  # short, medium, long
    target_section: Optional[str] = None
    custom_focus: Optional[str] = None
    summary_text: str
    key_points: List[str] = []
    technical_terms: Dict[str, str] = {}  # term: explanation
    confidence_score: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = {}

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class RecommendationSchema(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    document_id: PyObjectId
    user_id: PyObjectId
    recommendation_type: str  # paper, book, author
    title: str
    authors: List[str] = []
    publication_year: Optional[int] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    similarity_score: float
    recommendation_reason: str
    source: str  # semantic_scholar, crossref, manual
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_relevant: Optional[bool] = None  # user feedback

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class SessionSchema(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    session_token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_active: bool = True
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
