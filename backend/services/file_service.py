# backend/services/file_service.py
"""
File service for handling document uploads and processing.
Supports PDF, DOCX, and TXT files.
"""

import os
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging
import asyncio
from datetime import datetime

# Document processing libraries
import PyPDF2
from docx import Document as DocxDocument
import pdfplumber
import aiofiles
from PIL import Image
import pytesseract

from ..config.settings import settings
from ..models.document import DocumentType, DocumentMetadata, DocumentSection

logger = logging.getLogger(__name__)


class FileService:
    """Service for file handling and document processing."""
    
    def __init__(self):
        self.upload_folder = Path(settings.upload_folder)
        self.upload_folder.mkdir(exist_ok=True)
        self.max_file_size = settings.max_upload_size
        self.allowed_extensions = settings.allowed_extensions
    
    async def save_uploaded_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str
    ) -> Tuple[str, str, DocumentType]:
        """
        Save uploaded file and return file path, content hash, and type.
        """
        # Validate file
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            raise ValueError(f"File type {file_ext} not allowed")
        
        if len(file_content) > self.max_file_size:
            raise ValueError(f"File size exceeds maximum of {self.max_file_size} bytes")
        
        # Calculate content hash
        content_hash = hashlib.sha256(file_content).hexdigest()
        
        # Create user directory
        user_folder = self.upload_folder / user_id
        user_folder.mkdir(exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{content_hash[:8]}_{filename}"
        file_path = user_folder / safe_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        logger.info(f"Saved file: {file_path}")
        
        # Determine file type
        doc_type = DocumentType(file_ext[1:])  # Remove dot
        
        return str(file_path), content_hash, doc_type
    
    async def extract_text_content(
        self,
        file_path: str,
        doc_type: DocumentType
    ) -> Tuple[str, DocumentMetadata]:
        """
        Extract text content and metadata from document.
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            if doc_type == DocumentType.PDF:
                return await self._extract_from_pdf(file_path_obj)
            elif doc_type == DocumentType.DOCX:
                return await self._extract_from_docx(file_path_obj)
            elif doc_type == DocumentType.TXT:
                return await self._extract_from_txt(file_path_obj)
            else:
                raise ValueError(f"Unsupported document type: {doc_type}")
                
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {e}")
            raise
    
    async def _extract_from_pdf(self, file_path: Path) -> Tuple[str, DocumentMetadata]:
        """Extract content from PDF file."""
        content_parts = []
        metadata = DocumentMetadata()
        sections = []
        
        try:
            # Try pdfplumber first for better text extraction
            with pdfplumber.open(file_path) as pdf:
                metadata.total_pages = len(pdf.pages)
                
                # Extract text from each page
                current_section = None
                current_content = []
                
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    
                    # Simple section detection (can be improved)
                    lines = page_text.split('\n')
                    for line in lines:
                        # Check if line might be a section header
                        if self._is_section_header(line):
                            # Save previous section
                            if current_section and current_content:
                                sections.append(DocumentSection(
                                    title=current_section,
                                    content='\n'.join(current_content),
                                    page_numbers=[i]
                                ))
                            current_section = line.strip()
                            current_content = []
                        else:
                            current_content.append(line)
                    
                    content_parts.append(page_text)
                
                # Save last section
                if current_section and current_content:
                    sections.append(DocumentSection(
                        title=current_section,
                        content='\n'.join(current_content)
                    ))
                
                # Extract metadata from first page
                if pdf.pages and content_parts:
                    first_page_text = content_parts[0]
                    metadata.title = self._extract_title(first_page_text)
                    metadata.abstract = self._extract_abstract('\n'.join(content_parts))
                
        except Exception as e:
            logger.warning(f"pdfplumber failed, trying PyPDF2: {e}")
            
            # Fallback to PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata.total_pages = len(pdf_reader.pages)
                
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    content_parts.append(text)
        
        # Combine all content
        full_content = '\n\n'.join(content_parts)
        
        # Calculate statistics
        metadata.total_words = len(full_content.split())
        metadata.sections = sections
        
        return full_content, metadata
    
    async def _extract_from_docx(self, file_path: Path) -> Tuple[str, DocumentMetadata]:
        """Extract content from DOCX file."""
        doc = DocxDocument(file_path)
        content_parts = []
        metadata = DocumentMetadata()
        sections = []
        
        current_section = None
        current_content = []
        
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            
            if not text:
                continue
            
            # Check for section headers (usually have specific styles)
            if paragraph.style.name.startswith('Heading'):
                if current_section and current_content:
                    sections.append(DocumentSection(
                        title=current_section,
                        content='\n'.join(current_content)
                    ))
                current_section = text
                current_content = []
            else:
                current_content.append(text)
                content_parts.append(text)
        
        # Save last section
        if current_section and current_content:
            sections.append(DocumentSection(
                title=current_section,
                content='\n'.join(current_content)
            ))
        
        # Extract metadata
        full_content = '\n\n'.join(content_parts)
        metadata.title = self._extract_title(full_content)
        metadata.abstract = self._extract_abstract(full_content)
        metadata.total_words = len(full_content.split())
        metadata.sections = sections
        
        # Extract from document properties
        core_properties = doc.core_properties
        if core_properties.author:
            metadata.authors = [core_properties.author]
        
        return full_content, metadata
    
    async def _extract_from_txt(self, file_path: Path) -> Tuple[str, DocumentMetadata]:
        """Extract content from TXT file."""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        metadata = DocumentMetadata()
        metadata.total_words = len(content.split())
        
        # Try to extract basic metadata
        lines = content.split('\n')
        if lines:
            metadata.title = lines[0].strip()
        
        metadata.abstract = self._extract_abstract(content)
        
        return content, metadata
    
    async def process_ocr(self, file_path: str) -> Optional[str]:
        """
        Perform OCR on images in PDF if text extraction fails.
        """
        try:
            # This is a simplified version - in production, use more sophisticated OCR
            # Extract images from PDF and run OCR
            import fitz  # PyMuPDF
            
            pdf_document = fitz.open(file_path)
            text_parts = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # Get images
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    # Extract image
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        # Convert to PIL Image
                        img_data = pix.tobytes("png")
                        image = Image.open(io.BytesIO(img_data))
                        
                        # Run OCR
                        text = pytesseract.image_to_string(image)
                        text_parts.append(text)
                    
                    pix = None
            
            pdf_document.close()
            
            return '\n'.join(text_parts) if text_parts else None
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return None
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = path.stat()
        
        return {
            "filename": path.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "extension": path.suffix
        }
    
    def _is_section_header(self, line: str) -> bool:
        """Check if a line might be a section header."""
        line = line.strip()
        
        # Common section headers
        section_keywords = [
            "abstract", "introduction", "methodology", "methods",
            "results", "discussion", "conclusion", "references",
            "acknowledgments", "appendix"
        ]
        
        # Check if line is short and contains section keywords
        if len(line.split()) <= 3:
            lower_line = line.lower()
            return any(keyword in lower_line for keyword in section_keywords)
        
        # Check for numbered sections
        if line.split('.')[0].isdigit():
            return True
        
        return False
    
    def _extract_title(self, content: str) -> Optional[str]:
        """Extract title from document content."""
        lines = content.split('\n')
        
        # Usually title is in the first few lines
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            # Title is usually long enough but not too long
            if 10 <= len(line) <= 200 and not line.lower().startswith(('abstract', 'keywords')):
                return line
        
        return None
    
    def _extract_abstract(self, content: str) -> Optional[str]:
        """Extract abstract from document content."""
        lower_content = content.lower()
        
        # Find abstract section
        abstract_start = lower_content.find('abstract')
        if abstract_start == -1:
            return None
        
        # Find where abstract ends (usually at introduction or keywords)
        abstract_end = len(content)
        for end_marker in ['introduction', 'keywords', '1.', '\n\n\n']:
            pos = lower_content.find(end_marker, abstract_start + 8)
            if pos != -1 and pos < abstract_end:
                abstract_end = pos
        
        # Extract abstract
        abstract = content[abstract_start:abstract_end].strip()
        
        # Clean up
        if abstract.lower().startswith('abstract'):
            abstract = abstract[8:].strip()
        
        # Limit length
        words = abstract.split()
        if len(words) > 300:
            abstract = ' '.join(words[:300]) + '...'
        
        return abstract if len(abstract) > 50 else None


# Singleton instance
file_service = FileService()