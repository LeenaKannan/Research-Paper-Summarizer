# backend/routers/summarize.py
"""
Summary generation router.
Handles AI-powered summarization and related features.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
import logging
import json
import io
from datetime import datetime

from ..models.summary import (
    SummaryCreate, SummaryResponse, SummaryUpdate,
    SummaryListResponse, SummaryRegenerateRequest,
    BatchSummaryRequest, SummaryComparison,
    SummaryExportRequest, SummaryAnalytics,
    SummaryParameters
)
from ..models.document import DocumentStatus
from ..models.user import UserInDB
from ..services.ai_service import ai_service
from ..database.operations import DocumentOperations, SummaryOperations, UserOperations
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/summarize",
    tags=["summaries"]
)


@router.post("/", response_model=SummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_summary(
    summary_request: SummaryCreate,
    user: UserInDB = Depends(get_current_user)
):
    """
    Generate a summary for a document.
    
    Parameters can be customized for length, style, and focus areas.
    """
    # Verify document exists and user has access
    document = await DocumentOperations.get_document(summary_request.document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not ready for summarization (status: {document.status.value})"
        )
    
    try:
        # Generate summary using AI service
        summary_content, generation_metadata = await ai_service.generate_summary(
            document.content,
            document.metadata,
            summary_request.parameters,
            summary_request.custom_prompt
        )
        
        # Save summary to database
        summary_db = await SummaryOperations.create_summary(
            summary_request,
            summary_content.dict(),
            generation_metadata
        )
        
        logger.info(f"Summary created: {summary_db.id} for document {document.id}")
        
        return SummaryResponse(
            id=summary_db.id,
            document_id=summary_db.document_id,
            content=summary_db.content,
            parameters=summary_db.parameters,
            created_at=summary_db.created_at,
            model_used=summary_db.model_used,
            rating=summary_db.rating,
            is_favorite=summary_db.is_favorite,
            view_count=summary_db.view_count
        )
        
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary"
        )


@router.post("/batch", response_model=List[SummaryResponse])
async def create_batch_summaries(
    batch_request: BatchSummaryRequest,
    background_tasks: BackgroundTasks,
    user: UserInDB = Depends(get_current_user)
):
    """
    Generate summaries for multiple documents.
    
    Processing happens in the background.
    """
    summaries = []
    
    for document_id in batch_request.document_ids:
        # Verify document access
        document = await DocumentOperations.get_document(document_id)
        
        if not document or document.user_id != user.id:
            continue
        
        if document.status != DocumentStatus.READY:
            continue
        
        # Create summary request
        summary_request = SummaryCreate(
            document_id=document_id,
            user_id=user.id,
            parameters=batch_request.parameters
        )
        
        # Add to background task
        background_tasks.add_task(
            generate_summary_background,
            summary_request,
            document
        )
        
        # Return placeholder response
        summaries.append({
            "document_id": document_id,
            "status": "processing"
        })
    
    return summaries


async def generate_summary_background(summary_request: SummaryCreate, document):
    """Background task for summary generation."""
    try:
        summary_content, generation_metadata = await ai_service.generate_summary(
            document.content,
            document.metadata,
            summary_request.parameters,
            summary_request.custom_prompt
        )
        
        await SummaryOperations.create_summary(
            summary_request,
            summary_content.dict(),
            generation_metadata
        )
        
    except Exception as e:
        logger.error(f"Background summary generation failed: {e}")


@router.get("/", response_model=SummaryListResponse)
async def list_summaries(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    document_id: Optional[str] = None,
    user: UserInDB = Depends(get_current_user)
):
    """
    Get user's summaries with pagination.
    
    Can filter by document_id.
    """
    if document_id:
        # Get summaries for specific document
        summaries = await SummaryOperations.get_document_summaries(document_id)
        
        # Filter by user access
        summaries = [s for s in summaries if s.user_id == user.id]
        
        return SummaryListResponse(
            summaries=[
                SummaryResponse(
                    id=s.id,
                    document_id=s.document_id,
                    content=s.content,
                    parameters=s.parameters,
                    created_at=s.created_at,
                    model_used=s.model_used,
                    rating=s.rating,
                    is_favorite=s.is_favorite,
                    view_count=s.view_count
                )
                for s in summaries
            ],
            total=len(summaries),
            page=1,
            page_size=len(summaries)
        )
    
    else:
        # Get all user summaries
        result = await SummaryOperations.get_user_summaries(
            user.id,
            page,
            page_size
        )
        
        return SummaryListResponse(
            summaries=[
                SummaryResponse(
                    id=s.id,
                    document_id=s.document_id,
                    content=s.content,
                    parameters=s.parameters,
                    created_at=s.created_at,
                    model_used=s.model_used,
                    rating=s.rating,
                    is_favorite=s.is_favorite,
                    view_count=s.view_count
                )
                for s in result["summaries"]
            ],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"]
        )


@router.get("/{summary_id}", response_model=SummaryResponse)
async def get_summary(
    summary_id: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Get a specific summary by ID.
    """
    summary = await SummaryOperations.get_summary(summary_id)
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found"
        )
    
    # Check ownership
    if summary.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return SummaryResponse(
        id=summary.id,
        document_id=summary.document_id,
        content=summary.content,
        parameters=summary.parameters,
        created_at=summary.created_at,
        model_used=summary.model_used,
        rating=summary.rating,
        is_favorite=summary.is_favorite,
        view_count=summary.view_count
    )


@router.patch("/{summary_id}", response_model=SummaryResponse)
async def update_summary(
    summary_id: str,
    update_data: SummaryUpdate,
    user: UserInDB = Depends(get_current_user)
):
    """
    Update summary rating, feedback, or favorite status.
    """
    summary = await SummaryOperations.get_summary(summary_id)
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found"
        )
    
    # Check ownership
    if summary.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    updated_summary = await SummaryOperations.update_summary(summary_id, update_data)
    
    return SummaryResponse(
        id=updated_summary.id,
        document_id=updated_summary.document_id,
        content=updated_summary.content,
        parameters=updated_summary.parameters,
        created_at=updated_summary.created_at,
        model_used=updated_summary.model_used,
        rating=updated_summary.rating,
        is_favorite=updated_summary.is_favorite,
        view_count=updated_summary.view_count
    )


@router.post("/regenerate", response_model=SummaryResponse)
async def regenerate_summary(
    request: SummaryRegenerateRequest,
    user: UserInDB = Depends(get_current_user)
):
    """
    Regenerate a summary with new parameters.
    
    Creates a new summary version linked to the original.
    """
    # Get original summary
    original_summary = await SummaryOperations.get_summary(request.summary_id)
    
    if not original_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found"
        )
    
    if original_summary.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get document
    document = await DocumentOperations.get_document(original_summary.document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Use new parameters or original ones
    parameters = request.parameters or original_summary.parameters
    
    try:
        # Generate new summary
        summary_content, generation_metadata = await ai_service.generate_summary(
            document.content,
            document.metadata,
            parameters,
            request.custom_prompt
        )
        
        # Create summary request
        summary_create = SummaryCreate(
            document_id=document.id,
            user_id=user.id,
            parameters=parameters,
            custom_prompt=request.custom_prompt
        )
        
        # Add parent reference
        generation_metadata["parent_summary_id"] = request.summary_id
        generation_metadata["version"] = original_summary.version + 1
        
        # Preserve rating if requested
        if request.preserve_rating and original_summary.rating:
            generation_metadata["rating"] = original_summary.rating
        
        # Save new summary
        new_summary = await SummaryOperations.create_summary(
            summary_create,
            summary_content.dict(),
            generation_metadata
        )
        
        return SummaryResponse(
            id=new_summary.id,
            document_id=new_summary.document_id,
            content=new_summary.content,
            parameters=new_summary.parameters,
            created_at=new_summary.created_at,
            model_used=new_summary.model_used,
            rating=new_summary.rating,
            is_favorite=new_summary.is_favorite,
            view_count=new_summary.view_count
        )
        
    except Exception as e:
        logger.error(f"Summary regeneration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate summary"
        )


@router.post("/compare", response_model=SummaryComparison)
async def compare_summaries(
    document_id: str,
    summary_ids: List[str],
    user: UserInDB = Depends(get_current_user)
):
    """
    Compare multiple summaries of the same document.
    """
    if len(summary_ids) < 2 or len(summary_ids) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide 2-5 summary IDs to compare"
        )
    
    # Verify document access
    document = await DocumentOperations.get_document(document_id)
    if not document or document.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get summaries
    summaries = []
    for summary_id in summary_ids:
        summary = await SummaryOperations.get_summary(summary_id)
        if summary and summary.document_id == document_id and summary.user_id == user.id:
            summaries.append({
                "id": summary.id,
                "parameters": summary.parameters.dict(),
                "content": summary.content.main_summary,
                "created_at": summary.created_at.isoformat(),
                "rating": summary.rating
            })
    
    if len(summaries) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough valid summaries to compare"
        )
    
    # Simple comparison (in production, use NLP for better analysis)
    consensus_points = []
    conflicting_points = []
    
    return SummaryComparison(
        document_id=document_id,
        summaries=summaries,
        differences_highlighted={},
        consensus_points=consensus_points,
        conflicting_points=conflicting_points
    )


@router.post("/export")
async def export_summaries(
    export_request: SummaryExportRequest,
    user: UserInDB = Depends(get_current_user)
):
    """
    Export summaries in various formats.
    
    Supported formats: PDF, DOCX, Markdown, JSON
    """
    # Verify access to summaries
    summaries = []
    for summary_id in export_request.summary_ids:
        summary = await SummaryOperations.get_summary(summary_id)
        if summary and summary.user_id == user.id:
            summaries.append(summary)
    
    if not summaries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid summaries found"
        )
    
    # Export based on format
    if export_request.format == "json":
        # JSON export
        export_data = []
        for summary in summaries:
            data = {
                "summary_id": summary.id,
                "document_id": summary.document_id,
                "content": summary.content.dict(),
                "parameters": summary.parameters.dict(),
                "created_at": summary.created_at.isoformat(),
                "model_used": summary.model_used
            }
            
            if export_request.include_document_info:
                doc = await DocumentOperations.get_document(summary.document_id)
                if doc:
                    data["document"] = {
                        "title": doc.metadata.title,
                        "authors": doc.metadata.authors,
                        "filename": doc.original_filename
                    }
            
            export_data.append(data)
        
        json_content = json.dumps(export_data, indent=2)
        
        return StreamingResponse(
            io.StringIO(json_content),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=summaries_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
    
    elif export_request.format == "markdown":
        # Markdown export
        markdown_content = "# Research Paper Summaries\n\n"
        
        for summary in summaries:
            markdown_content += f"## Summary {summary.id}\n\n"
            
            if export_request.include_document_info:
                doc = await DocumentOperations.get_document(summary.document_id)
                if doc and doc.metadata.title:
                    markdown_content += f"**Document:** {doc.metadata.title}\n\n"
            
            markdown_content += f"**Generated:** {summary.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            markdown_content += f"### Summary\n\n{summary.content.main_summary}\n\n"
            
            if summary.content.key_points:
                markdown_content += "### Key Points\n\n"
                for point in summary.content.key_points:
                    markdown_content += f"- {point.text}\n"
                markdown_content += "\n"
            
            if export_request.include_metadata:
                markdown_content += f"**Model:** {summary.model_used}\n"
                markdown_content += f"**Type:** {summary.parameters.summary_type}\n"
                markdown_content += f"**Length:** {summary.parameters.summary_length}\n\n"
            
            markdown_content += "---\n\n"
        
        return StreamingResponse(
            io.StringIO(markdown_content),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=summaries_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
            }
        )
    
    else:
        # PDF and DOCX would require additional libraries
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Export format '{export_request.format}' not yet implemented"
        )


@router.post("/question")
async def answer_question(
    document_id: str,
    question: str,
    user: UserInDB = Depends(get_current_user)
):
    """
    Answer a question about a document using AI.
    """
    # Verify document access
    document = await DocumentOperations.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document not ready"
        )
    
    try:
        answer = await ai_service.answer_question(document.content, question)
        
        return {
            "document_id": document_id,
            "question": question,
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Question answering error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to answer question"
        )


@router.get("/analytics/me", response_model=SummaryAnalytics)
async def get_my_summary_analytics(user: UserInDB = Depends(get_current_user)):
    """
    Get summary analytics for the current user.
    """
    analytics = await SummaryOperations.get_summary_analytics(user.id)
    
    # Get summaries for this month
    summaries_this_month = 0  # Would calculate from database
    
    # Get topic distribution
    most_summarized_topics = []  # Would aggregate from summaries
    
    return SummaryAnalytics(
        user_id=user.id,
        total_summaries=analytics.get("total_summaries", 0),
        summaries_this_month=summaries_this_month,
        average_rating=analytics.get("average_rating", 0.0),
        most_summarized_topics=most_summarized_topics,
        preferred_length=user.preferences.summary_length,
        preferred_type=user.preferences.summary_style,
        total_exports=analytics.get("total_exports", 0),
        total_views=analytics.get("total_views", 0)
    )