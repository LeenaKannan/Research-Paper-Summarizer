# backend/services/ai_service.py
"""
AI service for OpenAI API integration.
Handles summary generation, text processing, and embeddings.
"""

import openai
from typing import List, Dict, Any, Optional, Tuple
import tiktoken
import logging
import json
from datetime import datetime
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import settings
from ..models.summary import SummaryParameters, SummaryType, SummaryLength, SummaryContent, KeyPoint
from ..models.document import DocumentMetadata

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai.api_key = settings.openai_api_key


class AIService:
    """Service for AI-powered text processing and generation."""
    
    def __init__(self):
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        self.encoding = tiktoken.encoding_for_model(self.model)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_summary(
        self,
        document_content: str,
        document_metadata: DocumentMetadata,
        parameters: SummaryParameters,
        custom_prompt: Optional[str] = None
    ) -> Tuple[SummaryContent, Dict[str, Any]]:
        """
        Generate a summary using OpenAI API.
        Returns the summary content and generation metadata.
        """
        start_time = datetime.utcnow()
        
        # Prepare the prompt
        prompt = self._build_summary_prompt(
            document_content,
            document_metadata,
            parameters,
            custom_prompt
        )
        
        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(parameters)
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            # Make API call
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                max_tokens=self._calculate_max_tokens(parameters),
                temperature=parameters.temperature,
                response_format={"type": "json_object"} if parameters.summary_type == SummaryType.EXTRACTIVE else None
            )
            
            # Parse response
            content = response.choices[0].message.content
            
            # Process based on summary type
            if parameters.summary_type == SummaryType.EXTRACTIVE:
                summary_data = json.loads(content)
            else:
                summary_data = self._parse_abstractive_summary(content)
            
            # Create summary content
            summary_content = SummaryContent(
                main_summary=summary_data.get("summary", ""),
                key_points=[
                    KeyPoint(
                        text=point.get("text", ""),
                        importance=point.get("importance", 0.5),
                        source_section=point.get("section")
                    )
                    for point in summary_data.get("key_points", [])
                ],
                extracted_keywords=summary_data.get("keywords", []),
                methodology_summary=summary_data.get("methodology"),
                findings_summary=summary_data.get("findings"),
                limitations=summary_data.get("limitations", []),
                future_work=summary_data.get("future_work", [])
            )
            
            # Calculate costs
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_cost = self._calculate_cost(prompt_tokens, completion_tokens)
            
            # Generation metadata
            generation_metadata = {
                "generation_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "model_used": self.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_cost": total_cost
            }
            
            logger.info(f"Generated summary: {len(summary_content.main_summary)} chars, cost: ${total_cost:.4f}")
            
            return summary_content, generation_metadata
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            raise
    
    async def extract_document_metadata(self, content: str) -> DocumentMetadata:
        """Extract metadata from document content using AI."""
        prompt = f"""
        Extract the following metadata from this research paper:
        - Title
        - Authors (list)
        - Abstract
        - Keywords (list)
        - Main topics (list)
        - Key findings (list)
        - Methodology (brief description)
        
        Document content:
        {content[:3000]}...
        
        Return as JSON.
        """
        
        messages = [
            {
                "role": "system",
                "content": "You are a research paper metadata extractor. Extract accurate metadata and return it as valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            metadata_dict = json.loads(response.choices[0].message.content)
            
            return DocumentMetadata(
                title=metadata_dict.get("title"),
                authors=metadata_dict.get("authors", []),
                abstract=metadata_dict.get("abstract"),
                keywords=metadata_dict.get("keywords", []),
                main_topics=metadata_dict.get("main_topics", []),
                key_findings=metadata_dict.get("key_findings", []),
                methodology=metadata_dict.get("methodology")
            )
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return DocumentMetadata()
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text using OpenAI."""
        try:
            response = await openai.Embedding.acreate(
                model="text-embedding-ada-002",
                input=text[:8000]  # Limit text length
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    async def answer_question(self, document_content: str, question: str) -> str:
        """Answer a question about the document."""
        prompt = f"""
        Based on the following document, answer the question concisely and accurately.
        If the answer is not in the document, say so.
        
        Document:
        {document_content[:4000]}...
        
        Question: {question}
        """
        
        messages = [
            {
                "role": "system",
                "content": "You are a helpful research assistant. Answer questions based solely on the provided document."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.5
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            raise
    
    def _build_summary_prompt(
        self,
        content: str,
        metadata: DocumentMetadata,
        parameters: SummaryParameters,
        custom_prompt: Optional[str]
    ) -> str:
        """Build the prompt for summary generation."""
        # Start with base prompt
        prompt_parts = []
        
        if custom_prompt:
            prompt_parts.append(custom_prompt)
        else:
            prompt_parts.append("Please summarize the following research paper.")
        
        # Add parameters
        length_words = {
            SummaryLength.SHORT: 100,
            SummaryLength.MEDIUM: 300,
            SummaryLength.LONG: 500,
            SummaryLength.CUSTOM: parameters.target_word_count or 300
        }
        
        target_words = length_words.get(parameters.summary_length, 300)
        prompt_parts.append(f"Target length: approximately {target_words} words.")
        
        if parameters.simplify_technical:
            prompt_parts.append("Simplify technical jargon for a general audience.")
        
        if parameters.focus_topics:
            prompt_parts.append(f"Focus on these topics: {', '.join(parameters.focus_topics)}")
        
        if parameters.exclude_topics:
            prompt_parts.append(f"Exclude these topics: {', '.join(parameters.exclude_topics)}")
        
        # Add document info
        if metadata.title:
            prompt_parts.append(f"\nTitle: {metadata.title}")
        
        if metadata.authors:
            prompt_parts.append(f"Authors: {', '.join(metadata.authors[:5])}")
        
        # Add content
        prompt_parts.append(f"\nDocument content:\n{content[:8000]}...")
        
        return "\n".join(prompt_parts)
    
    def _get_system_prompt(self, parameters: SummaryParameters) -> str:
        """Get the system prompt based on parameters."""
        base_prompt = "You are an expert research paper summarizer."
        
        if parameters.summary_type == SummaryType.EXTRACTIVE:
            return f"{base_prompt} Extract key sentences and return a structured JSON summary."
        elif parameters.summary_type == SummaryType.ABSTRACTIVE:
            return f"{base_prompt} Create a flowing, coherent summary that captures the essence of the paper."
        else:
            return f"{base_prompt} Create a mixed summary combining extraction and abstraction."
    
    def _calculate_max_tokens(self, parameters: SummaryParameters) -> int:
        """Calculate max tokens based on summary length."""
        length_tokens = {
            SummaryLength.SHORT: 200,
            SummaryLength.MEDIUM: 600,
            SummaryLength.LONG: 1000,
            SummaryLength.CUSTOM: min(parameters.target_word_count * 2 if parameters.target_word_count else 600, 2000)
        }
        
        return length_tokens.get(parameters.summary_length, 600)
    
    def _parse_abstractive_summary(self, content: str) -> Dict[str, Any]:
        """Parse abstractive summary into structured format."""
        # Simple parsing - in production, use more sophisticated NLP
        lines = content.strip().split("\n")
        
        summary_data = {
            "summary": content,
            "key_points": [],
            "keywords": []
        }
        
        # Extract key points (lines starting with bullets or numbers)
        for line in lines:
            if line.strip().startswith(("•", "-", "*", "1.", "2.", "3.")):
                summary_data["key_points"].append({
                    "text": line.strip().lstrip("•-*123456789. "),
                    "importance": 0.8
                })
        
        return summary_data
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate API cost based on tokens."""
        prompt_cost_per_1k = 0.03
        completion_cost_per_1k = 0.06
        
        total_cost = (
            (prompt_tokens / 1000) * prompt_cost_per_1k +
            (completion_tokens / 1000) * completion_cost_per_1k
        )
        
        return round(total_cost, 4)


# Singleton instance
ai_service = AIService()