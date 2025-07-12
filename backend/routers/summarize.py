# backend/models/summary.py
"""
Summary data models and schemas.
Defines summary-related data structures for AI-generated summaries.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class SummaryType(str, Enum):
    """Summary type enumeration."""
    ABSTRACTIVE = "abstractive"
    EXTRACTIVE = "extractive"
    MIXED = "mixed"


class SummaryLength(str, Enum):
    """Summary length options."""
    SHORT = "short"  # ~100 words
    MEDIUM = "medium"  # ~300 words
    LONG = "long"  # ~500 words
    CUSTOM = "custom"


class SummarySection(str, Enum):
    """Document sections that can be summarized."""
    FULL = "full"
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSIONS = "conclusions"
    CUSTOM = "custom"


class SummaryParameters(BaseModel):
    """Parameters for summary generation."""
    summary_type: SummaryType = SummaryType.ABSTRACTIVE
    summary_length: SummaryLength = SummaryLength.MEDIUM
    target_word_count: Optional[int] = None
    sections_to_include: List[SummarySection] = [SummarySection.FULL]
    simplify_technical: bool = False
    include_keywords: bool = True
    include_citations: bool = False
    language: str = "en"
    
    # Advanced parameters
    temperature: float = 0.7
    focus_topics: List[str] = []
    exclude_topics: List[str] = []
    
    @validator('target_word_count')
    def validate_word_count(cls, v, values):
        """Validate custom word count."""
        if values.get('summary_length') == SummaryLength.CUSTOM and v is None:
            raise ValueError('target_word_count required when summary_length is CUSTOM')
        if v is not None and (v < 50 or v > 1000):
            raise ValueError('target_word_count must be between 50 and 1000')
        return v


class SummaryBase(BaseModel):
    """Base summary schema."""
    document_id: str
    user_id: str
    parameters: SummaryParameters


class SummaryCreate(SummaryBase):
    """Schema for creating a new summary."""
    custom_prompt: Optional[str] = None
    
    @validator('custom_prompt')
    def validate_prompt(cls, v):
        """Validate custom prompt length."""
        if v and len(v) > 500:
            raise ValueError('Custom prompt must be less than 500 characters')
        return v


class KeyPoint(BaseModel):
    """Represents a key point in the summary."""
    text: str
    importance: float  # 0-1 score
    source_section: Optional[str] = None
    page_reference: Optional[int] = None


class SummaryContent(BaseModel):
    """Generated summary content."""
    main_summary: str
    key_points: List[KeyPoint] = []
    extracted_keywords: List[str] = []
    methodology_summary: Optional[str] = None
    findings_summary: Optional[str] = None
    limitations: List[str] = []
    future_work: List[str] = []
    
    # Statistics
    word_count: int = 0
    sentence_count: int = 0
    
    @validator('word_count', always=True)
    def calculate_word_count(cls, v, values):
        """Calculate word count from main summary."""
        if v == 0 and 'main_summary' in values:
            return len(values['main_summary'].split())
        return v


class SummaryInDB(SummaryBase):
    """Summary schema as stored in database."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Generated content
    content: SummaryContent
    
    # Generation metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    generation_time_seconds: float
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    total_cost: float = 0.0
    
    # User interaction
    rating: Optional[int] = None  # 1-5 stars
    feedback: Optional[str] = None
    is_favorite: bool = False
    view_count: int = 0
    last_viewed: Optional[datetime] = None
    
    # Versioning
    version: int = 1
    parent_summary_id: Optional[str] = None  # For regenerated summaries
    
    # Export tracking
    exported_count: int = 0
    last_exported: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SummaryResponse(BaseModel):
    """Summary schema for API responses."""
    id: str
    document_id: str
    content: SummaryContent
    parameters: SummaryParameters
    created_at: datetime
    model_used: str
    rating: Optional[int]
    is_favorite: bool
    view_count: int
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SummaryListResponse(BaseModel):
    """Response schema for summary list endpoints."""
    summaries: List[SummaryResponse]
    total: int
    page: int
    page_size: int


class SummaryUpdate(BaseModel):
    """Schema for updating summary information."""
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback: Optional[str] = None
    is_favorite: Optional[bool] = None


class SummaryRegenerateRequest(BaseModel):
    """Request to regenerate a summary with new parameters."""
    summary_id: str
    parameters: Optional[SummaryParameters] = None
    custom_prompt: Optional[str] = None
    preserve_rating: bool = True


class BatchSummaryRequest(BaseModel):
    """Request for batch summary generation."""
    document_ids: List[str]
    parameters: SummaryParameters
    
    @validator('document_ids')
    def validate_document_ids(cls, v):
        """Limit batch size."""
        if len(v) > 10:
            raise ValueError('Maximum 10 documents per batch')
        if len(set(v)) != len(v):
            raise ValueError('Duplicate document IDs not allowed')
        return v


class SummaryComparison(BaseModel):
    """Compare multiple summaries of the same document."""
    document_id: str
    summaries: List[Dict[str, Any]]
    differences_highlighted: Dict[str, List[str]]
    consensus_points: List[str]
    conflicting_points: List[Dict[str, str]]


class SummaryExportRequest(BaseModel):
    """Request to export summaries."""
    summary_ids: List[str]
    format: str = "pdf"  # pdf, docx, markdown, json
    include_metadata: bool = True
    include_document_info: bool = True
    
    @validator('format')
    def validate_format(cls, v):
        allowed_formats = ['pdf', 'docx', 'markdown', 'json']
        if v not in allowed_formats:
            raise ValueError(f'Format must be one of {allowed_formats}')
        return v


class SummaryAnalytics(BaseModel):
    """Analytics for summary usage."""
    user_id: str
    total_summaries: int
    summaries_this_month: int
    average_rating: float
    most_summarized_topics: List[Dict[str, int]]
    preferred_length: str
    preferred_type: str
    total_exports: int
    total_views: int