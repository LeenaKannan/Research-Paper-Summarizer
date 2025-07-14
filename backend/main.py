# backend/main.py
"""
Main FastAPI application entry point.
Configures the API server with all routers and middleware.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any
import uvicorn

from .config.settings import settings
from .database.connection import db_manager
from .routers import auth, upload, summarize

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting AI Research Paper Summarizer API...")
    
    # Connect to database
    try:
        await db_manager.connect()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise
    
    # Initialize other services if needed
    logger.info("API startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API...")
    
    # Disconnect from database
    await db_manager.disconnect()
    
    logger.info("API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    AI-powered Research Paper Summarizer API
    
    ## Features
    
    * **Document Upload**: Support for PDF, DOCX, and TXT files
    * **AI Summarization**: Generate high-quality summaries using GPT-4
    * **Customization**: Control summary length, style, and focus areas
    * **Smart Recommendations**: Find similar papers and related content
    * **User Management**: Secure authentication and user preferences
    * **Export Options**: Download summaries in various formats
    
    ## Authentication
    
    Most endpoints require authentication. Use the `/auth/login` endpoint to obtain a JWT token.
    Include the token in the `Authorization` header as `Bearer <token>`.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure based on your deployment
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Custom middleware for request timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Custom middleware for rate limiting (simplified version)
request_counts: Dict[str, Dict[str, Any]] = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware."""
    # Skip rate limiting for docs and health check
    if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
        return await call_next(request)
    
    # Get client IP
    client_ip = request.client.host
    
    # Check rate limit
    current_time = time.time()
    if client_ip in request_counts:
        request_data = request_counts[client_ip]
        if current_time - request_data["window_start"] > settings.rate_limit_period:
            # Reset window
            request_counts[client_ip] = {
                "count": 1,
                "window_start": current_time
            }
        elif request_data["count"] >= settings.rate_limit_requests:
            # Rate limit exceeded
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
        else:
            # Increment count
            request_counts[client_ip]["count"] += 1
    else:
        # First request from this IP
        request_counts[client_ip] = {
            "count": 1,
            "window_start": current_time
        }
    
    response = await call_next(request)
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Don't expose internal errors in production
    if settings.debug:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error": str(exc)
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )


# Include routers
app.include_router(
    auth.router,
    prefix=f"{settings.api_v1_prefix}"
)

app.include_router(
    upload.router,
    prefix=f"{settings.api_v1_prefix}"
)

app.include_router(
    summarize.router,
    prefix=f"{settings.api_v1_prefix}"
)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to AI Research Paper Summarizer API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the API status and database connectivity.
    """
    try:
        # Check database connection
        db_status = "connected" if db_manager.database else "disconnected"
        
        # You can add more health checks here
        # - Redis connection
        # - OpenAI API availability
        # - Storage availability
        
        return {
            "status": "healthy",
            "version": settings.app_version,
            "database": db_status,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# API info endpoint
@app.get("/info", tags=["info"])
async def api_info():
    """Get API configuration information."""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": "production" if not settings.debug else "development",
        "features": {
            "max_upload_size_mb": settings.max_upload_size / (1024 * 1024),
            "allowed_file_types": list(settings.allowed_extensions),
            "ai_model": settings.openai_model,
            "rate_limit": {
                "requests": settings.rate_limit_requests,
                "period_seconds": settings.rate_limit_period
            }
        }
    }


# Metrics endpoint (simplified)
@app.get("/metrics", tags=["monitoring"])
async def metrics():
    """
    Get basic API metrics.
    
    In production, use Prometheus or similar monitoring tools.
    """
    return {
        "active_connections": len(request_counts),
        "database_connected": db_manager.database is not None,
        "uptime_seconds": time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
    }


# Store start time
@app.on_event("startup")
async def record_start_time():
    app.state.start_time = time.time()


# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
        access_log=True
    )