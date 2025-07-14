# backend/routers/upload.py
"""
File upload router.
Handles document upload, processing, and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from typing import List, Optional
import logging
import aiofiles
from pathlib import Path

from ..models.document import (
    DocumentResponse, DocumentListResponse, DocumentCreate,
    DocumentUpdate, DocumentStatus, DocumentSearchQuery,
    SimilarDocumentRequest, DocumentAnalytics
)
from ..models.user import UserInDB
from ..services.file_service import file_service
from ..services.ai_service import ai_service
from ..database.operations import DocumentOperations, UserOperations
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/upload",
    tags=["documents"]
)


async def process_document_background(document_id: str, file_path: str, doc_type: str):
    """Background task to process uploaded document."""
    try:
        # Extract text content
        content, metadata = await file_service.extract_text_content(file_path, doc_type)
        
        # Generate embeddings
        embeddings = await ai_service.generate_embeddings(content[:8000])
        
        # Extract metadata using AI
        if not metadata.title or not metadata.abstract:
            ai_metadata = await ai_service.extract_document_metadata(content)
            metadata.title = metadata.title or ai_metadata.title
            metadata.abstract = metadata.abstract or ai_metadata.abstract
            metadata.keywords = metadata.keywords or ai_metadata.keywords
            metadata.main_topics = ai_metadata.main_topics
            metadata.key_findings = ai_metadata.key_findings
        
        # Update document in database
        update_data = DocumentUpdate(
            content=content,
            metadata=metadata,
            status=DocumentStatus.READY,
            content_embedding=embeddings
        )
        
        await DocumentOperations.update_document(document_id, update_data)
        
        logger.info(f"Document processed successfully: {document_id}")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        
        # Update document status to failed
        await DocumentOperations.update_document(
            document_id,
            DocumentUpdate(
                status=DocumentStatus.FAILED,
                error_message=str(e)
            )
        )


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: UserInDB = Depends(get_current_user)
):
    """
    Upload a research paper.
    
    Supported formats: PDF, DOCX, TXT
    Maximum file size: 10MB
    """
    try:
        # Read file content
        content = await file.read()
        
        # Save file
        file_path, content_hash, doc_type = await file_service.save_uploaded_file(
            content,
            file.filename,
            user.id
        )
        
        # Create document record
        doc_create = DocumentCreate(
            filename=Path(file_path).name,
            original_filename=file.filename,
            file_type=doc_type,
            file_size=len(content),
            content_hash=content_hash,
            user_id=user.id,
            file_path=file_path
        )
        
        document = await DocumentOperations.create_document(doc_create)
        
        # Process document in background
        background_tasks.add_task(
            process_document_background,
            document.id,
            file_path,
            doc_type
        )
        
        logger.info(f"Document uploaded: {document.id} by user {user.username}")
        
        return DocumentResponse(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            upload_date=document.upload_date,
            processed_date=document.processed_date,
            metadata=document.metadata,
            tags=document.tags,
            notes=document.notes,
            is_favorite=document.is_favorite
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.post("/batch", response_model=List[DocumentResponse])
async def upload_documents_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    user: UserInDB = Depends(get_current_user)
):
    """
    Upload multiple documents at once.
    
    Maximum 5 files per batch.
    """
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 files per batch"
        )
    
    uploaded_documents = []
    
    for file in files:
        try:
            # Read file content
            content = await file.read()
            
            # Save file
            file_path, content_hash, doc_type = await file_service.save_uploaded_file(
                content,
                file.filename,
                user.id
            )
            
            # Create document record
            doc_create = DocumentCreate(
                filename=Path(file_path).name,
                original_filename=file.filename,
                file_type=doc_type,
                file_size=len(content),
                content_hash=content_hash,
                user_id=user.id,
                file_path=file_path
            )
            
            document = await DocumentOperations.create_document(doc_create)
            
            # Process document in background
            background_tasks.add_task(
                process_document_background,
                document.id,
                file_path,
                doc_type
            )
            
            uploaded_documents.append(DocumentResponse(
                id=document.id,
                filename=document.filename,
                original_filename=document.original_filename,
                file_type=document.file_type,
                file_size=document.file_size,
                status=document.status,
                upload_date=document.upload_date,
                processed_date=document.processed_date,
                metadata=document.metadata,
                tags=document.tags,
                notes=document.notes,
                is_favorite=document.is_favorite
            ))
            
        except Exception as e:
            logger.error(f"Error uploading {file.filename}: {e}")
            # Continue with other files
    
    return uploaded_documents


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[DocumentStatus] = None,
    user: UserInDB = Depends(get_current_user)
):
    """
    Get user's documents with pagination.
    """
    result = await DocumentOperations.get_user_documents(
        user.id,
        page,
        page_size,
        status
    )
    
    documents = [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            upload_date=doc.upload_date,
            processed_date=doc.processed_date,
            metadata=doc.metadata,
            tags=doc.tags,
            notes=doc.notes,
            is_favorite=doc.is_favorite
        )
        for doc in result["documents"]
    ]
    
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"]
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Get a specific document by ID.
    """
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        upload_date=document.upload_date,
        processed_date=document.processed_date,
        metadata=document.metadata,
        tags=document.tags,
        notes=document.notes,
        is_favorite=document.is_favorite
    )


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Get the extracted text content of a document.
    """
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is {document.status.value}"
        )
    
    return {
        "document_id": document.id,
        "content": document.content,
        "metadata": document.metadata
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Download the original document file.
    """
    from fastapi.responses import FileResponse
    
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(
        path=file_path,
        filename=document.original_filename,
        media_type="application/octet-stream"
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    update_data: DocumentUpdate,
    user: UserInDB = Depends(get_current_user)
):
    """
    Update document metadata, tags, or notes.
    """
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    updated_document = await DocumentOperations.update_document(document_id, update_data)
    
    return DocumentResponse(
        id=updated_document.id,
        filename=updated_document.filename,
        original_filename=updated_document.original_filename,
        file_type=updated_document.file_type,
        file_size=updated_document.file_size,
        status=updated_document.status,
        upload_date=updated_document.upload_date,
        processed_date=updated_document.processed_date,
        metadata=updated_document.metadata,
        tags=updated_document.tags,
        notes=updated_document.notes,
        is_favorite=updated_document.is_favorite
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Delete a document (soft delete).
    """
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    success = await DocumentOperations.delete_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )
    
    # Update user storage
    await UserOperations.increment_user_stats(
        user.id,
        "storage_used_mb",
        -(document.file_size / (1024 * 1024))
    )


@router.post("/search", response_model=List[DocumentResponse])
async def search_documents(
    query: DocumentSearchQuery,
    user: UserInDB = Depends(get_current_user)
):
    """
    Search documents using full-text search.
    """
    documents = await DocumentOperations.search_documents(
        user.id,
        query.query,
        query.page_size
    )
    
    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            upload_date=doc.upload_date,
            processed_date=doc.processed_date,
            metadata=doc.metadata,
            tags=doc.tags,
            notes=doc.notes,
            is_favorite=doc.is_favorite
        )
        for doc in documents
    ]


@router.post("/{document_id}/similar", response_model=List[DocumentResponse])
async def find_similar_documents(
    document_id: str,
    request: SimilarDocumentRequest,
    user: UserInDB = Depends(get_current_user)
):
    """
    Find similar documents based on content similarity.
    """
    # This would use vector similarity search on embeddings
    # Simplified implementation for now
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # In a real implementation, use vector database for similarity search
    # For now, return empty list
    return []


@router.get("/{document_id}/analytics", response_model=DocumentAnalytics)
async def get_document_analytics(
    document_id: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Get analytics for a document.
    """
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check ownership
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Calculate analytics
    word_count = len(document.content.split()) if document.content else 0
    reading_time = word_count // 250  # Average reading speed
    
    return DocumentAnalytics(
        document_id=document.id,
        reading_time_minutes=reading_time,
        complexity_score=0.7,  # Placeholder
        readability_score=60.0,  # Placeholder
        topic_distribution={},  # Placeholder
        citation_network=[],  # Placeholder
        key_concepts=document.metadata.keywords,
        summary_views=0,  # Would track in real implementation
        download_count=0  # Would track in real implementation
    )