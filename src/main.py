"""
FastAPI Application Entry Point for SEC Event Intelligence API
===============================================================

This module initializes and configures the FastAPI application with:
- Middleware (CORS, rate limiting, logging, security headers)
- Error handlers
- Route registration
- Health checks
- Startup/shutdown events

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import (
    add_rate_limit_headers,
    router as api_router,
)
from src.config import settings
from src.models.schemas import ErrorResponse, HealthResponse

# ============================================
# LOGGING SETUP
# ============================================

# Configure logging
logging.basicConfig(
    level=settings.logging.level.value,
    format=settings.logging.format,
    handlers=[
        logging.StreamHandler(),
    ]
)

# Add file handler if configured
if settings.logging.file_path:
    from logging.handlers import RotatingFileHandler
    
    file_handler = RotatingFileHandler(
        filename=settings.logging.file_path,
        maxBytes=settings.logging.max_file_size,
        backupCount=settings.logging.backup_count,
    )
    file_handler.setFormatter(logging.Formatter(settings.logging.format))
    logging.getLogger().addHandler(file_handler)

# Configure JSON logging if enabled
if settings.logging.json_format:
    import json
    from pythonjsonlogger import jsonlogger
    
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            log_record['timestamp'] = datetime.now().isoformat()
            log_record['level'] = record.levelname
            log_record['logger'] = record.name
    
    json_handler = logging.StreamHandler()
    json_handler.setFormatter(CustomJsonFormatter())
    logging.getLogger().handlers = [json_handler]

# Get logger
logger = logging.getLogger(__name__)
logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
logger.info(f"📋 Environment: {settings.environment.value}")
logger.info(f"🔧 Debug mode: {settings.debug}")


# ============================================
# REQUEST ID MIDDLEWARE
# ============================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID to every request.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Add to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response


# ============================================
# REQUEST LOGGING MIDDLEWARE
# ============================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests with timing information.
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get request details
        request_id = getattr(request.state, "request_id", "unknown")
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request
        logger.info(
            f"📥 Request {request_id} - {method} {url} from {client_ip}"
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"📤 Response {request_id} - {method} {url} - "
                f"{response.status_code} in {duration:.2f}ms"
            )
            
            return response
            
        except Exception as e:
            # Log error
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"❌ Error {request_id} - {method} {url} - "
                f"{type(e).__name__}: {str(e)} in {duration:.2f}ms"
            )
            raise


# ============================================
# ERROR HANDLERS
# ============================================

async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle HTTP exceptions.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # Log error
    logger.error(
        f"HTTP {exc.status_code}: {exc.detail} - {request.url} "
        f"(request_id: {request_id})"
    )
    
    # Build error response
    error_response = ErrorResponse(
        error=f"HTTP_{exc.status_code}",
        message=str(exc.detail) if exc.detail else "HTTP error occurred",
        status_code=exc.status_code,
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle validation errors.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # Extract validation errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })
    
    # Log error
    logger.warning(
        f"Validation error: {errors} - {request.url} "
        f"(request_id: {request_id})"
    )
    
    # Build error response
    error_response = ErrorResponse(
        error="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        request_id=request_id,
        details={"errors": errors},
        path=str(request.url.path),
        method=request.method,
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )


async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle unhandled exceptions.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # Log error with traceback
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)} - "
        f"{request.url} (request_id: {request_id})",
        exc_info=True
    )
    
    # Build error response
    error_response = ErrorResponse(
        error="INTERNAL_ERROR",
        message="An internal error occurred. Please try again later.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
    )
    
    # Include details in development
    if settings.is_development:
        error_response.details = {
            "exception": type(exc).__name__,
            "message": str(exc),
        }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


# ============================================
# LIFESPAN MANAGER
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan manager for startup and shutdown events.
    """
    # === STARTUP ===
    logger.info("🔄 Starting up...")
    
    # Log configuration (redacted)
    logger.info(f"📋 Configuration:")
    logger.info(f"   - Environment: {settings.environment.value}")
    logger.info(f"   - Debug: {settings.debug}")
    logger.info(f"   - Host: {settings.host}:{settings.port}")
    logger.info(f"   - Workers: {settings.workers}")
    logger.info(f"   - Rate Limit (Free): {settings.rate_limit.free} req/min")
    logger.info(f"   - Rate Limit (Pro): {settings.rate_limit.pro} req/min")
    logger.info(f"   - Rate Limit (Ultra): {settings.rate_limit.ultra} req/min")
    logger.info(f"   - Rate Limit (Mega): {settings.rate_limit.mega} req/min")
    logger.info(f"   - Cache TTL: {settings.cache.default_ttl}s")
    logger.info(f"   - Cache Max Size: {settings.cache.max_size}")
    
    # Initialize connections if needed
    # (Services will be initialized lazily)
    
    logger.info("✅ Startup complete")
    
    # === RUN ===
    yield
    
    # === SHUTDOWN ===
    logger.info("🔄 Shutting down...")
    
    # Clean up connections
    # (Services will be cleaned up when garbage collected)
    
    logger.info("✅ Shutdown complete")


# ============================================
# CREATE FASTAPI APPLICATION
# ============================================

app = FastAPI(
    title=settings.api.title,
    description=settings.api.description,
    version=settings.api.version,
    docs_url=settings.api.docs_url if settings.is_development else None,
    redoc_url=settings.api.redoc_url if settings.is_development else None,
    openapi_url=settings.api.openapi_url if settings.is_development else None,
    lifespan=lifespan,
    # Custom OpenAPI tags
    openapi_tags=[
        {
            "name": "SEC Event Intelligence",
            "description": "Endpoints for retrieving and classifying SEC events",
        },
        {
            "name": "Company Search",
            "description": "Search for companies by name, ticker, or CIK",
        },
        {
            "name": "System",
            "description": "System endpoints (health, metrics, pricing)",
        },
    ],
)


# ============================================
# MIDDLEWARE
# ============================================

# Trusted Hosts (for production)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure appropriately for production
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Estimated-Cost-Per-Request",
        "X-Current-Tier",
        "X-RateLimit-Warning",
        "X-Overage-Billed",
        "X-Upgrade-Suggested",
        "X-Response-Time",
    ],
)

# Request ID
app.add_middleware(RequestIDMiddleware)

# Request Logging
app.add_middleware(RequestLoggingMiddleware)

# Rate Limit Headers (from routes)
app.middleware("http")(add_rate_limit_headers)


# ============================================
# ERROR HANDLERS
# ============================================

# Register error handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


# ============================================
# ROUTES
# ============================================

# Include API routes
app.include_router(api_router)


# ============================================
# ROOT ENDPOINTS
# ============================================

@app.get(
    "/",
    tags=["System"],
    summary="API Root",
    description="Welcome endpoint with API information",
)
async def root() -> Dict[str, Any]:
    """
    Root endpoint with API information.
    """
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment.value,
        "docs": "/docs" if settings.is_development else None,
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
    }


@app.get(
    "/health",
    tags=["System"],
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API health and dependencies",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    """
    # Check dependencies
    dependencies = {
        "SEC EDGAR": True,  # Will be checked on first request
        "Cache": True,       # Always available
    }
    
    # Check SEC API if service is initialized
    try:
        from src.services.sec import SECService
        sec = SECService()
        # Just check if client is available
        dependencies["SEC EDGAR"] = True
    except Exception as e:
        logger.warning(f"SEC EDGAR health check failed: {e}")
        dependencies["SEC EDGAR"] = False
    
    # Calculate uptime
    from src.api.routes import _get_uptime
    
    return HealthResponse(
        status="healthy" if all(dependencies.values()) else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
        timestamp=datetime.now().isoformat(),
        uptime=_get_uptime(),
        dependencies=dependencies,
    )


@app.get(
    "/health/live",
    tags=["System"],
    summary="Liveness Probe",
    description="Kubernetes liveness probe",
)
async def liveness_probe() -> PlainTextResponse:
    """
    Liveness probe for container orchestration.
    """
    return PlainTextResponse("OK", status_code=200)


@app.get(
    "/health/ready",
    tags=["System"],
    summary="Readiness Probe",
    description="Kubernetes readiness probe",
)
async def readiness_probe() -> PlainTextResponse:
    """
    Readiness probe for container orchestration.
    """
    # Check dependencies
    try:
        from src.services.sec import SECService
        sec = SECService()
        if client is None:
            return PlainTextResponse("SEC EDGAR client unavailable", status_code=503)
        return PlainTextResponse("OK", status_code=200)
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return PlainTextResponse(str(e), status_code=503)


@app.get(
    "/metrics",
    tags=["System"],
    summary="Metrics Endpoint",
    description="Prometheus metrics endpoint (if enabled)",
)
async def metrics() -> PlainTextResponse:
    """
    Prometheus metrics endpoint.
    """
    if not settings.monitoring.prometheus_enabled:
        return PlainTextResponse("Metrics disabled", status_code=404)
    
    try:
        from prometheus_client import generate_latest
        return PlainTextResponse(generate_latest(), media_type="text/plain")
    except ImportError:
        return PlainTextResponse("Prometheus client not installed", status_code=501)
    except Exception as e:
        logger.error(f"Metrics generation failed: {e}")
        return PlainTextResponse(str(e), status_code=500)


# ============================================
# OPENAPI CUSTOMIZATION
# ============================================

def customize_openapi():
    """
    Customize the OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = app.openapi()
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication. Get your key from your dashboard.",
        },
        "RapidAPIKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-RapidAPI-Key",
            "description": "RapidAPI key for marketplace users.",
        },
    }
    
    # Add global security
    openapi_schema["security"] = [
        {"APIKeyHeader": []},
        {"RapidAPIKey": []},
    ]
    
    # Add contact information
    openapi_schema["info"]["contact"] = {
        "name": "YASEN-ALPHA Support",
        "email": "emmayasenchak@gmail.com",
        "url": "https://github.com/yasen-alpha/sec-event-intelligence-api",
    }
    
    # Add license
    openapi_schema["info"]["license"] = {
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override the OpenAPI schema
app.openapi = customize_openapi


# ============================================
# SERVER CONFIGURATION
# ============================================

def run():
    """
    Run the application with uvicorn.
    """
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        workers=settings.workers if settings.is_production else 1,
        log_level=settings.logging.level.value.lower(),
        access_log=settings.is_development,
    )


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    run()


# ============================================
# EXPORTS
# ============================================

__all__ = [
    "app",
    "run",
]