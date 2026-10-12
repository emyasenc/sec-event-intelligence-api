"""
API Routes for SEC Event Intelligence API
===========================================

This module contains all FastAPI route handlers for the SEC Event Intelligence API.
It provides endpoints for:
- SEC filing event retrieval and classification
- Company search and enrichment
- Batch processing for multiple companies
- Health checks and monitoring
- Rate limiting and caching

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.config import settings
from src.core.cache import Cache
from src.core.rate_limiter import RateLimiter
from src.models.schemas import (
    BatchEventRequest,
    CompanySearchResult,
    ErrorResponse,
    EventResponse,
    PricingResponse,
    PricingTier,
    SECEvent,
)
from src.services.classifier import EventClassifier
from src.services.enricher import CompanyEnricher
from src.services.extractor import FactExtractor
from src.services.sec import SECService
from src.utils.validators import (
    validate_company_query,
    validate_event_type,
    validate_form_type,
)

# ============================================
# LOGGING SETUP
# ============================================

logger = logging.getLogger(__name__)
logger.setLevel(settings.logging.level.value)


class StructuredLogger:
    """Structured logging wrapper for production observability"""

    @staticmethod
    def _create_context(request_id: str, **kwargs) -> Dict[str, Any]:
        """Create structured log context"""
        return {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment.value,
            **kwargs
        }

    @classmethod
    def info(cls, message: str, request_id: str = None, **kwargs):
        context = cls._create_context(request_id or str(uuid.uuid4()), **kwargs)
        logger.info(message, extra={"context": context})

    @classmethod
    def error(cls, message: str, request_id: str = None, **kwargs):
        context = cls._create_context(request_id or str(uuid.uuid4()), **kwargs)
        logger.error(message, extra={"context": context})

    @classmethod
    def warning(cls, message: str, request_id: str = None, **kwargs):
        context = cls._create_context(request_id or str(uuid.uuid4()), **kwargs)
        logger.warning(message, extra={"context": context})

    @classmethod
    def debug(cls, message: str, request_id: str = None, **kwargs):
        context = cls._create_context(request_id or str(uuid.uuid4()), **kwargs)
        logger.debug(message, extra={"context": context})


structured_logger = StructuredLogger()

# ============================================
# ROUTER & SERVICE INSTANCES
# ============================================

router = APIRouter(
    prefix="/api/v1",
    tags=["SEC Event Intelligence"],
    responses={
        400: {"description": "Bad Request", "model": ErrorResponse},
        404: {"description": "Not Found", "model": ErrorResponse},
        429: {"description": "Too Many Requests", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    }
)

# Service instances (singleton pattern via dependency injection)
_sec_service: Optional[SECService] = None
_classifier: Optional[EventClassifier] = None
_extractor: Optional[FactExtractor] = None
_enricher: Optional[CompanyEnricher] = None

# Cache instances
_events_cache: Optional[Cache] = None
_company_cache: Optional[Cache] = None

# Rate limiter
_rate_limiter: Optional[RateLimiter] = None

# Service uptime tracker
_start_time = datetime.now()


def get_sec_service() -> SECService:
    """Dependency injection for SEC Service"""
    global _sec_service
    if _sec_service is None:
        _sec_service = SECService()
    return _sec_service


def get_classifier() -> EventClassifier:
    """Dependency injection for Event Classifier"""
    global _classifier
    if _classifier is None:
        _classifier = EventClassifier()
    return _classifier


def get_extractor() -> FactExtractor:
    """Dependency injection for Fact Extractor"""
    global _extractor
    if _extractor is None:
        _extractor = FactExtractor()
    return _extractor


def get_enricher() -> CompanyEnricher:
    """Dependency injection for Company Enricher"""
    global _enricher
    if _enricher is None:
        _enricher = CompanyEnricher()
    return _enricher


def get_events_cache() -> Cache:
    """Dependency injection for Events Cache"""
    global _events_cache
    if _events_cache is None:
        _events_cache = Cache(
            ttl=settings.cache.default_ttl,
            max_size=settings.cache.max_size,
            namespace="sec_events"
        )
    return _events_cache


def get_company_cache() -> Cache:
    """Dependency injection for Company Cache"""
    global _company_cache
    if _company_cache is None:
        _company_cache = Cache(
            ttl=86400 * 7,  # 7 days for company data
            max_size=settings.cache.max_size,
            namespace="sec_companies"
        )
    return _company_cache


def get_rate_limiter() -> RateLimiter:
    """Dependency injection for Rate Limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def _get_uptime() -> str:
    """Calculate service uptime"""
    uptime = datetime.now() - _start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


# ============================================
# PRICING TIERS
# ============================================

PRICING_TIERS = {
    "free": {
        "name": "Free",
        "price": 0,
        "requests_per_month": 500,
        "rate_limit": 10,
        "features": [
            "Event classification",
            "8-K events only",
            "Company search",
            "Up to 20 results per request",
            "Community support",
            "No credit card required"
        ]
    },
    "pro": {
        "name": "Pro",
        "price": 25,
        "requests_per_month": 10000,
        "rate_limit": 20,
        "features": [
            "Everything in Free",
            "All form types (10-K, 10-Q, 8-K, S-1)",
            "Fact extraction with source evidence",
            "Batch queries (up to 50 companies)",
            "Webhook support",
            "Email support",
            "Cost transparency headers"
        ]
    },
    "ultra": {
        "name": "Ultra",
        "price": 75,
        "requests_per_month": 50000,
        "rate_limit": 40,
        "features": [
            "Everything in Pro",
            "Priority support",
            "Higher rate limits",
            "Advanced filtering",
            "Custom event types",
            "SLA 99.9% uptime",
            "Soft rate limiting with overage billing",
            "Dedicated account manager"
        ]
    },
    "mega": {
        "name": "Mega",
        "price": 150,
        "requests_per_month": 200000,
        "rate_limit": 60,
        "features": [
            "Everything in Ultra",
            "Dedicated support",
            "Custom integrations",
            "White-label options",
            "Enterprise SLA",
            "Volume discounts available",
            "Private endpoint options",
            "Custom data enrichment"
        ]
    }
}


# ============================================
# RATE LIMITING (Simple IP-based for RapidAPI)
# ============================================

async def get_client_id(request: Request) -> str:
    """Extract client identifier from request for rate limiting"""
    # For RapidAPI, use the RapidAPI key or IP
    api_key = (
        request.headers.get("X-RapidAPI-Key") or
        request.headers.get("X-API-Key") or
        request.query_params.get("api_key")
    )
    
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12]
        return f"api_key_{key_hash}"
    
    # Fallback to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    
    return f"ip_{client_ip}"


async def get_rate_limit_config(request: Request) -> Dict[str, Any]:
    """Determine rate limit configuration based on client"""
    # Default to free tier
    return {
        "limit": PRICING_TIERS["free"]["rate_limit"],
        "window": 60,
        "tier": "free",
    }


async def check_rate_limit(request: Request) -> None:
    """Rate limiting dependency for API endpoints"""
    client_id = await get_client_id(request)
    config = await get_rate_limit_config(request)
    rate_limiter = get_rate_limiter()
    
    is_allowed, remaining, reset_time = rate_limiter.check_rate_limit(
        client_id=client_id,
        limit=config["limit"],
        window=config["window"]
    )
    
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset_time
    request.state.rate_limit_limit = config["limit"]
    request.state.rate_limit_tier = config["tier"]
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Maximum {config['limit']} requests per minute.",
                "limit": config["limit"],
                "window": config["window"],
                "remaining": 0,
                "reset_at": reset_time.isoformat() if reset_time else None,
                "timestamp": datetime.now().isoformat(),
                "tier": config["tier"],
            }
        )


# ============================================
# HELPER FUNCTIONS
# ============================================

def create_error_response(
    error_code: str,
    message: str,
    request_id: Optional[str] = None,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    error = {
        "error": error_code,
        "message": message,
        "request_id": request_id or str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
    }
    if details:
        error["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=error
    )


async def get_events_for_company(
    query: str,
    form_type: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 20,
    request_id: Optional[str] = None
) -> Optional[EventResponse]:
    validated_query = validate_company_query(query)
    if not validated_query:
        return None
    
    cache_key = f"events_{validated_query}_{form_type or 'all'}_{event_type or 'all'}_{limit}"
    events_cache = get_events_cache()
    
    cached_result = events_cache.get(cache_key)
    if cached_result:
        return EventResponse(**cached_result)
    
    sec_service = get_sec_service()
    classifier = get_classifier()
    
    try:
        company = await sec_service.search_company(validated_query)
        if not company:
            return EventResponse(
                total=0,
                events=[],
                timestamp=datetime.now().isoformat()
            )
        
        filings = await sec_service.get_filings(
            cik=company["cik"],
            form_type=form_type,
            limit=limit
        )
        
        events = []
        for filing in filings:
            classified_events = classifier.classify_filing(filing)
            for event in classified_events:
                events.append(event)
        
        # FIXED: event is a SECEvent object, not a dict
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # FIXED: events are already SECEvent objects, no need to convert
        result = EventResponse(
            total=len(events),
            events=events[:limit],
            timestamp=datetime.now().isoformat()
        )
        
        events_cache.set(cache_key, result.dict())
        return result
        
    except Exception as e:
        structured_logger.error(
            f"Error processing {validated_query}: {str(e)}",
            request_id=request_id
        )
        raise


async def process_events_batch(
    queries: List[str],
    form_type: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 10,
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    semaphore = asyncio.Semaphore(10)
    
    async def process_single(query: str) -> Dict[str, Any]:
        async with semaphore:
            try:
                result = await get_events_for_company(
                    query=query,
                    form_type=form_type,
                    event_type=event_type,
                    limit=limit,
                    request_id=request_id
                )
                return {
                    "query": query,
                    "success": True,
                    "data": result.dict() if result else {"total": 0, "events": []}
                }
            except Exception as e:
                return {
                    "query": query,
                    "success": False,
                    "error": str(e)
                }
    
    tasks = [process_single(query) for query in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


# ============================================
# MAIN ENDPOINTS
# ============================================

@router.get(
    "/events",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get SEC filing events for a company",
    description="Retrieve and classify SEC events (8-K, 10-K, 10-Q) for any public company.",
    dependencies=[Depends(check_rate_limit)]
)
async def get_events(
    query: str = Query(..., description="Company name, ticker, or CIK"),
    form_type: Optional[str] = Query(None, description="Filter by form type"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of events"),
    request: Request = None,
) -> EventResponse:
    request_id = str(uuid.uuid4())
    
    validated_query = validate_company_query(query)
    if not validated_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_QUERY",
                "message": f"Invalid company query: {query}",
                "request_id": request_id,
            }
        )
    
    result = await get_events_for_company(
        query=validated_query,
        form_type=form_type,
        event_type=event_type,
        limit=limit,
        request_id=request_id
    )
    
    if not result:
        return EventResponse(total=0, events=[], timestamp=datetime.now().isoformat())
    
    return result


@router.post(
    "/events/batch",
    response_model=List[EventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get SEC events for multiple companies",
    description="Batch request for up to 50 companies.",
    dependencies=[Depends(check_rate_limit)]
)
async def get_events_batch(
    request_data: BatchEventRequest,
    request: Request = None,
) -> List[EventResponse]:
    request_id = str(uuid.uuid4())
    
    if len(request_data.queries) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "BATCH_TOO_LARGE",
                "message": f"Batch size {len(request_data.queries)} exceeds maximum of 50",
            }
        )
    
    results = await process_events_batch(
        queries=request_data.queries,
        form_type=request_data.form_type,
        event_type=request_data.event_type,
        limit=request_data.limit or 20,
        request_id=request_id
    )
    
    event_responses = []
    for result in results:
        if isinstance(result, dict) and result.get("success", False) and result.get("data"):
            event_responses.append(EventResponse(**result["data"]))
        else:
            event_responses.append(EventResponse(
                total=0,
                events=[],
                timestamp=datetime.now().isoformat()
            ))
    
    return event_responses


@router.get(
    "/company/search",
    response_model=List[CompanySearchResult],
    status_code=status.HTTP_200_OK,
    summary="Search for companies",
    description="Search for companies by name, ticker, or CIK.",
    dependencies=[Depends(check_rate_limit)]
)
async def search_companies(
    query: str = Query(..., description="Company name, ticker, or CIK"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    request: Request = None,
    sec_service: SECService = Depends(get_sec_service),
    enricher: CompanyEnricher = Depends(get_enricher),
) -> List[CompanySearchResult]:
    request_id = str(uuid.uuid4())
    
    validated_query = validate_company_query(query)
    if not validated_query:
        return []
    
    company_cache = get_company_cache()
    cache_key = f"company_search_{validated_query}_{limit}"
    
    cached_result = company_cache.get(cache_key)
    if cached_result:
        return [CompanySearchResult(**r) for r in cached_result]
    
    companies = await sec_service.search_companies(validated_query, limit=limit)
    if not companies:
        return []
    
    results = []
    for company in companies[:limit]:
        enriched = enricher.enrich_company(company)
        results.append(CompanySearchResult(**enriched))
    
    company_cache.set(cache_key, [r.dict() for r in results])
    
    return results


@router.get(
    "/pricing",
    response_model=PricingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get pricing information",
)
async def get_pricing() -> PricingResponse:
    tiers = {
        "free": PricingTier(
            name=PRICING_TIERS["free"]["name"],
            price=PRICING_TIERS["free"]["price"],
            requests_per_month=PRICING_TIERS["free"]["requests_per_month"],
            rate_limit=PRICING_TIERS["free"]["rate_limit"],
            features=PRICING_TIERS["free"]["features"]
        ),
        "pro": PricingTier(
            name=PRICING_TIERS["pro"]["name"],
            price=PRICING_TIERS["pro"]["price"],
            requests_per_month=PRICING_TIERS["pro"]["requests_per_month"],
            rate_limit=PRICING_TIERS["pro"]["rate_limit"],
            features=PRICING_TIERS["pro"]["features"]
        ),
        "ultra": PricingTier(
            name=PRICING_TIERS["ultra"]["name"],
            price=PRICING_TIERS["ultra"]["price"],
            requests_per_month=PRICING_TIERS["ultra"]["requests_per_month"],
            rate_limit=PRICING_TIERS["ultra"]["rate_limit"],
            features=PRICING_TIERS["ultra"]["features"]
        ),
        "mega": PricingTier(
            name=PRICING_TIERS["mega"]["name"],
            price=PRICING_TIERS["mega"]["price"],
            requests_per_month=PRICING_TIERS["mega"]["requests_per_month"],
            rate_limit=PRICING_TIERS["mega"]["rate_limit"],
            features=PRICING_TIERS["mega"]["features"]
        )
    }
    return PricingResponse(tiers=tiers)


@router.get(
    "/events/types",
    status_code=status.HTTP_200_OK,
    summary="Get all available event types",
)
async def get_event_types() -> Dict[str, Any]:
    return {
        "event_types": {
            "cybersecurity": {
                "description": "Cybersecurity breaches, incidents, and remediation",
                "subtypes": ["breach", "incident", "investigation", "remediation"]
            },
            "acquisition": {
                "description": "Mergers, acquisitions, and divestitures",
                "subtypes": ["asset_purchase", "stock_purchase", "merger", "divestiture"]
            },
            "auditor_change": {
                "description": "Auditor changes and disagreements",
                "subtypes": ["dismissal", "resignation", "engagement", "disagreement"]
            },
            "executive_change": {
                "description": "Executive departures, appointments, and compensation changes",
                "subtypes": ["departure", "appointment", "resignation", "termination"]
            },
            "bankruptcy": {
                "description": "Bankruptcy filings and related events",
                "subtypes": ["chapter_11", "chapter_7", "reorganization"]
            },
            "risk_factor": {
                "description": "Risk factor updates and disclosures",
                "subtypes": ["update", "new", "removal"]
            },
            "financial_statement": {
                "description": "Financial statement restatements and updates",
                "subtypes": ["restatement", "amendment", "correction"]
            },
            "regulation": {
                "description": "Regulatory changes and compliance updates",
                "subtypes": ["new_regulation", "change", "compliance"]
            }
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================
# RATE LIMIT HEADER MIDDLEWARE
# ============================================

async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    
    if hasattr(request.state, 'rate_limit_remaining'):
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
    if hasattr(request.state, 'rate_limit_limit'):
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)
    if hasattr(request.state, 'rate_limit_reset'):
        reset_time = request.state.rate_limit_reset
        if isinstance(reset_time, datetime):
            response.headers["X-RateLimit-Reset"] = str(int(reset_time.timestamp()))
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    return response


__all__ = [
    "router",
    "add_rate_limit_headers",
    "PRICING_TIERS",
]
