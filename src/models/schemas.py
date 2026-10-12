"""
Pydantic Schemas for SEC Event Intelligence API
================================================

This module defines all data models and schemas used throughout the SEC Event Intelligence API.
It provides:
- Request/response validation
- Data serialization/deserialization
- Type safety and validation
- API documentation generation

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic.types import PastDate, FutureDate


# ============================================
# ENUMS & CONSTANTS
# ============================================

class EventType(str, Enum):
    """Available SEC event types"""
    CYBERSECURITY = "cybersecurity"
    ACQUISITION = "acquisition"
    AUDITOR_CHANGE = "auditor_change"
    EXECUTIVE_CHANGE = "executive_change"
    BANKRUPTCY = "bankruptcy"
    RISK_FACTOR = "risk_factor"
    FINANCIAL_STATEMENT = "financial_statement"
    REGULATION = "regulation"
    OTHER = "other"
    SHARE_REPURCHASE = "share_repurchase"
    DEBT_FINANCING = "debt_financing"
    DIVIDEND = "dividend"
    LITIGATION = "litigation"

class FormType(str, Enum):
    """SEC form types"""
    FORM_8K = "8-K"
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_S1 = "S-1"
    FORM_S3 = "S-3"
    FORM_S4 = "S-4"
    FORM_DEF14A = "DEF14A"
    FORM_PRE14A = "PRE14A"
    FORM_SC13G = "SC 13G"
    FORM_SC13D = "SC 13D"
    FORM_144 = "144"


class Tier(str, Enum):
    """Pricing tiers"""
    FREE = "free"
    PRO = "pro"
    ULTRA = "ultra"
    MEGA = "mega"


# ============================================
# BASE MODELS
# ============================================

class BaseModelWithTimestamps(BaseModel):
    """Base model with timestamp fields"""
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp"
    )
    
    @field_validator("updated_at", mode="before")
    @classmethod
    def validate_updated_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure updated_at is not in the future"""
        if v and v > datetime.now():
            raise ValueError("updated_at cannot be in the future")
        return v


class BaseModelWithRequestId(BaseModel):
    """Base model with request ID tracking"""
    
    request_id: Optional[str] = Field(
        None,
        description="Unique request identifier for tracing",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    
    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate request ID format"""
        if v:
            try:
                # Try to parse as UUID
                UUID(v)
            except ValueError:
                # If not a UUID, ensure it's a valid format
                if not v.replace("-", "").isalnum() or len(v) > 64:
                    raise ValueError("Invalid request_id format")
        return v


# ============================================
# SEC FILING MODELS
# ============================================

class SECFiling(BaseModel):
    """SEC filing metadata"""
    
    accession_number: str = Field(
        ...,
        description="SEC accession number",
        examples=["0000320193-23-000106"]
    )
    form_type: FormType = Field(
        ...,
        description="SEC form type"
    )
    filing_date: datetime = Field(
        ...,
        description="Filing date",
        examples=["2024-01-15T00:00:00"]
    )
    company_name: str = Field(
        ...,
        description="Company name",
        min_length=1,
        max_length=255,
        examples=["Apple Inc."]
    )
    company_cik: str = Field(
        ...,
        description="Company CIK number",
        pattern=r"^\d{10}$",
        examples=["0000320193"]
    )
    ticker: Optional[str] = Field(
        None,
        description="Stock ticker symbol",
        min_length=1,
        max_length=10,
        examples=["AAPL"]
    )
    sic_code: Optional[str] = Field(
        None,
        description="SIC code",
        pattern=r"^\d{4}$",
        examples=["7370"]
    )
    industry: Optional[str] = Field(
        None,
        description="Industry classification",
        examples=["Computer Programming, Data Processing"]
    )
    description: Optional[str] = Field(
        None,
        description="Filing description",
        examples=["Form 8-K: Cybersecurity Incident"]
    )
    filing_url: HttpUrl = Field(
        ...,
        description="URL to the filing",
        examples=["https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm"]
    )
    document_url: HttpUrl = Field(
        ...,
        description="URL to the primary document",
        examples=["https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20240115.htm"]
    )
    items: Optional[List[str]] = Field(
        None,
        description="SEC item numbers covered",
        examples=[["1.01", "2.02"]]
    )
    source_text: Optional[str] = Field(
        None,
        description="Raw text from the filing (for classification)"
    )
    
    @field_validator("filing_date", mode="before")
    @classmethod
    def parse_filing_date(cls, v: Union[str, datetime]) -> datetime:
        """Parse various date formats"""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                # Try common SEC date format
                from dateutil import parser
                return parser.parse(v)
        raise ValueError(f"Invalid filing date format: {v}")
    
    class Config:
        json_schema_extra = {
            "example": {
                "accession_number": "0000320193-23-000106",
                "form_type": "8-K",
                "filing_date": "2024-01-15T00:00:00",
                "company_name": "Apple Inc.",
                "company_cik": "0000320193",
                "ticker": "AAPL",
                "sic_code": "7370",
                "industry": "Computer Programming, Data Processing",
                "description": "Form 8-K: Cybersecurity Incident",
                "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm",
                "document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20240115.htm",
                "items": ["1.01", "2.02"]
            }
        }


class SECEvent(BaseModel):
    """SEC event model (classified from filings)"""
    
    event_type: EventType = Field(
        ...,
        description="Event classification",
        examples=["cybersecurity"]
    )
    event_subtype: Optional[str] = Field(
        None,
        description="Event sub-classification",
        examples=["breach", "incident"]
    )
    sec_item: str = Field(
        ...,
        description="SEC item number",
        examples=["1.05"]
    )
    date: str = Field(
        ...,
        description="Event date",
        examples=["2024-01-15"]
    )
    description: str = Field(
        ...,
        description="Event description",
        min_length=1,
        max_length=1000,
        examples=["Cybersecurity breach reported"]
    )
    company_name: str = Field(
        ...,
        description="Company name",
        examples=["Apple Inc."]
    )
    ticker: Optional[str] = Field(
        None,
        description="Stock ticker symbol",
        examples=["AAPL"]
    )
    cik: str = Field(
        ...,
        description="CIK number",
        pattern=r"^\d{10}$",
        examples=["0000320193"]
    )
    filing_url: HttpUrl = Field(
        ...,
        description="Link to the source filing",
        examples=["https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm"]
    )
    source_text: str = Field(
        ...,
        description="Exact text from the filing (source evidence)",
        min_length=1,
        examples=["On January 12, 2024, Apple Inc. detected unauthorized access..."]
    )
    facts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted facts from the event",
        examples=[{"date": "2024-01-12", "severity": "HIGH", "systems_affected": ["Apple ID"]}]
    )
    accession_number: Optional[str] = Field(
        None,
        description="SEC accession number",
        examples=["0000320193-23-000106"]
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for event classification (0-1)",
        examples=[0.95]
    )
    evidence_references: List[Dict[str, str]] = Field(
        default_factory=list,
        description="References to evidence in the source text",
        examples=[[{"text": "Unauthorized access detected", "position": "line 42"}]]
    )
    
    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format"""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            # Try common formats
            from dateutil import parser
            try:
                parsed = parser.parse(v)
                return parsed.isoformat()
            except:
                raise ValueError(f"Invalid date format: {v}")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "cybersecurity",
                "event_subtype": "breach",
                "sec_item": "1.05",
                "date": "2024-01-15",
                "description": "Cybersecurity breach reported",
                "company_name": "Apple Inc.",
                "ticker": "AAPL",
                "cik": "0000320193",
                "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm",
                "source_text": "On January 12, 2024, Apple Inc. detected unauthorized access...",
                "facts": {"date": "2024-01-12", "severity": "HIGH"},
                "accession_number": "0000320193-23-000106",
                "confidence_score": 0.95
            }
        }


class CompanySearchResult(BaseModel):
    """Company search result model"""
    
    name: str = Field(
        ...,
        description="Company name",
        min_length=1,
        max_length=255,
        examples=["Apple Inc."]
    )
    ticker: Optional[str] = Field(
        None,
        description="Stock ticker symbol",
        min_length=1,
        max_length=10,
        examples=["AAPL"]
    )
    cik: str = Field(
        ...,
        description="CIK number",
        pattern=r"^\d{10}$",
        examples=["0000320193"]
    )
    sic_code: Optional[str] = Field(
        None,
        description="SIC code",
        pattern=r"^\d{4}$",
        examples=["7370"]
    )
    industry: Optional[str] = Field(
        None,
        description="Industry classification",
        examples=["Computer Programming, Data Processing"]
    )
    exchange: Optional[str] = Field(
        None,
        description="Stock exchange",
        examples=["NASDAQ", "NYSE"]
    )
    sector: Optional[str] = Field(
        None,
        description="Sector",
        examples=["Technology"]
    )
    headquarters: Optional[str] = Field(
        None,
        description="Headquarters location",
        examples=["Cupertino, CA"]
    )
    founded_year: Optional[int] = Field(
        None,
        ge=1800,
        le=datetime.now().year,
        description="Year founded",
        examples=[1976]
    )
    website: Optional[HttpUrl] = Field(
        None,
        description="Company website",
        examples=["https://www.apple.com"]
    )
    description: Optional[str] = Field(
        None,
        description="Company description",
        max_length=2000,
        examples=["Apple Inc. designs, manufactures, and markets smartphones..." ]
    )
    recent_filings: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Recent filing metadata",
        examples=[[{"form": "10-K", "date": "2023-09-30"}]]
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Search confidence score",
        examples=[0.98]
    )
    
    @field_validator("ticker", mode="before")
    @classmethod
    def validate_ticker(cls, v: Optional[str]) -> Optional[str]:
        """Validate ticker format"""
        if v:
            # Check for common ticker patterns
            if not v.isalnum() and not all(c.isalnum() or c == '.' for c in v):
                raise ValueError(f"Invalid ticker format: {v}")
            v = v.upper()
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Apple Inc.",
                "ticker": "AAPL",
                "cik": "0000320193",
                "sic_code": "7370",
                "industry": "Computer Programming, Data Processing",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "headquarters": "Cupertino, CA",
                "founded_year": 1976,
                "website": "https://www.apple.com",
                "description": "Apple Inc. designs, manufactures, and markets smartphones..."
            }
        }


# ============================================
# REQUEST MODELS
# ============================================

class FilingEventRequest(BaseModel):
    """Request model for filing events"""
    
    query: str = Field(
        ...,
        description="Company name, ticker, or CIK",
        min_length=1,
        max_length=100,
        examples=["AAPL", "Apple Inc.", "0000320193"]
    )
    form_type: Optional[FormType] = Field(
        None,
        description="Filter by form type",
        examples=[FormType.FORM_8K]
    )
    event_type: Optional[EventType] = Field(
        None,
        description="Filter by event type",
        examples=[EventType.CYBERSECURITY]
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of events to return",
        examples=[20, 50]
    )
    from_date: Optional[PastDate] = Field(
        None,
        description="Filter by date range (from)",
        examples=["2023-01-01"]
    )
    to_date: Optional[PastDate] = Field(
        None,
        description="Filter by date range (to)",
        examples=["2024-12-31"]
    )
    include_raw_text: bool = Field(
        default=False,
        description="Include raw filing text in response"
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for events",
        examples=[0.75]
    )
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean query"""
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        if len(v) < 1:
            raise ValueError("Query must be at least 1 character")
        return v
    
    @model_validator(mode="after")
    def validate_date_range(self) -> "FilingEventRequest":
        """Validate that from_date <= to_date"""
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before or equal to to_date")
        return self


class BatchEventRequest(BaseModel):
    """Batch request for multiple companies"""
    
    queries: List[str] = Field(
        ...,
        description="List of company names, tickers, or CIKs",
        min_length=1,
        max_length=50,
        examples=[["AAPL", "MSFT", "GOOGL"]]
    )
    form_type: Optional[FormType] = Field(
        None,
        description="Filter by form type (applied to all queries)",
        examples=[FormType.FORM_8K]
    )
    event_type: Optional[EventType] = Field(
        None,
        description="Filter by event type (applied to all queries)",
        examples=[EventType.CYBERSECURITY]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of events per company",
        examples=[10, 20]
    )
    parallel: bool = Field(
        default=True,
        description="Process queries in parallel"
    )
    max_concurrent: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum concurrent requests"
    )
    
    @field_validator("queries")
    @classmethod
    def validate_queries(cls, v: List[str]) -> List[str]:
        """Validate and clean queries"""
        if not v:
            raise ValueError("At least one query is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 queries allowed")
        # Remove duplicates while preserving order
        seen = set()
        cleaned = []
        for q in v:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                cleaned.append(q)
        return cleaned


# ============================================
# RESPONSE MODELS
# ============================================

class EventResponse(BaseModelWithRequestId):
    """Event response model"""
    
    total: int = Field(
        ...,
        ge=0,
        description="Total number of events found",
        examples=[15]
    )
    events: List[SECEvent] = Field(
        default_factory=list,
        description="List of classified events"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Response timestamp"
    )
    next_cursor: Optional[str] = Field(
        None,
        description="Pagination cursor for next page",
        examples=["eyJwYWdlIjogMn0="]
    )
    has_more: bool = Field(
        default=False,
        description="Whether there are more events available"
    )
    
    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Union[str, datetime]) -> str:
        """Validate timestamp format"""
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, str):
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
                return v
            except ValueError:
                from dateutil import parser
                parsed = parser.parse(v)
                return parsed.isoformat()
        raise ValueError(f"Invalid timestamp format: {v}")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 15,
                "events": [
                    {
                        "event_type": "cybersecurity",
                        "event_subtype": "breach",
                        "sec_item": "1.05",
                        "date": "2024-01-15",
                        "description": "Cybersecurity breach reported",
                        "company_name": "Apple Inc.",
                        "ticker": "AAPL",
                        "cik": "0000320193",
                        "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm",
                        "source_text": "On January 12, 2024, Apple Inc. detected unauthorized access...",
                        "facts": {"date": "2024-01-12", "severity": "HIGH"},
                        "confidence_score": 0.95
                    }
                ],
                "timestamp": "2024-01-15T10:30:00.123456",
                "request_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class CompanySearchResponse(BaseModelWithRequestId):
    """Company search response model"""
    
    total: int = Field(
        ...,
        ge=0,
        description="Total number of companies found",
        examples=[5]
    )
    companies: List[CompanySearchResult] = Field(
        default_factory=list,
        description="List of companies matching the search"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Response timestamp"
    )


class FilingDetailsResponse(BaseModelWithRequestId):
    """Detailed filing response model"""
    
    filing: SECFiling = Field(
        ...,
        description="Filing metadata"
    )
    events: List[SECEvent] = Field(
        default_factory=list,
        description="Classified events from this filing"
    )
    raw_text: Optional[str] = Field(
        None,
        description="Raw filing text (if requested)"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Response timestamp"
    )


# ============================================
# PRICING & METRICS MODELS
# ============================================

class PricingTier(BaseModel):
    """Pricing tier information"""
    
    name: str = Field(
        ...,
        description="Tier name",
        examples=["Pro"]
    )
    price: int = Field(
        ...,
        ge=0,
        description="Monthly price in USD",
        examples=[19]
    )
    requests_per_month: int = Field(
        ...,
        ge=0,
        description="Requests per month",
        examples=[10000]
    )
    rate_limit: int = Field(
        ...,
        ge=0,
        description="Rate limit (requests per minute)",
        examples=[20]
    )
    features: List[str] = Field(
        default_factory=list,
        description="Features included",
        examples=[["Everything in Free", "All form types", "Fact extraction"]]
    )
    overage_price: Optional[float] = Field(
        None,
        ge=0.0,
        description="Price per additional request beyond quota",
        examples=[0.002]
    )
    soft_limit_warning: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Percentage of quota that triggers a warning",
        examples=[80]
    )


class PricingResponse(BaseModel):
    """Pricing response model"""
    
    tiers: Dict[str, PricingTier] = Field(
        ...,
        description="Map of tier names to pricing information",
        examples=[{
            "free": {
                "name": "Free",
                "price": 0,
                "requests_per_month": 500,
                "rate_limit": 10,
                "features": ["Event classification", "8-K events only"]
            }
        }]
    )
    currency: str = Field(
        default="USD",
        description="Currency for pricing"
    )
    billing_cycle: str = Field(
        default="monthly",
        description="Billing cycle"
    )
    last_updated: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Last pricing update timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tiers": {
                    "free": {
                        "name": "Free",
                        "price": 0,
                        "requests_per_month": 500,
                        "rate_limit": 10,
                        "features": [
                            "Event classification",
                            "8-K events only",
                            "Company search"
                        ]
                    },
                    "pro": {
                        "name": "Pro",
                        "price": 19,
                        "requests_per_month": 10000,
                        "rate_limit": 20,
                        "features": [
                            "Everything in Free",
                            "All form types",
                            "Fact extraction"
                        ]
                    }
                },
                "currency": "USD",
                "billing_cycle": "monthly",
                "last_updated": "2024-01-15T10:30:00.123456"
            }
        }


class UsageMetrics(BaseModel):
    """Usage metrics for a client"""
    
    client_id: str = Field(
        ...,
        description="Client identifier",
        examples=["api_key_abc123def456"]
    )
    tier: Tier = Field(
        ...,
        description="Current tier",
        examples=[Tier.PRO]
    )
    requests_used: int = Field(
        ...,
        ge=0,
        description="Requests used in current period",
        examples=[4567]
    )
    requests_limit: int = Field(
        ...,
        ge=0,
        description="Request limit for current period",
        examples=[10000]
    )
    requests_remaining: int = Field(
        ...,
        ge=0,
        description="Requests remaining in current period",
        examples=[5433]
    )
    period_start: datetime = Field(
        ...,
        description="Current period start date"
    )
    period_end: datetime = Field(
        ...,
        description="Current period end date"
    )
    rate_limit_current: int = Field(
        ...,
        ge=0,
        description="Current rate limit (requests per minute)",
        examples=[20]
    )
    overage_used: float = Field(
        default=0.0,
        ge=0.0,
        description="Overage charges in current period",
        examples=[2.45]
    )
    estimated_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated cost for current period",
        examples=[21.45]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "api_key_abc123def456",
                "tier": "pro",
                "requests_used": 4567,
                "requests_limit": 10000,
                "requests_remaining": 5433,
                "period_start": "2024-01-01T00:00:00",
                "period_end": "2024-01-31T23:59:59",
                "rate_limit_current": 20,
                "overage_used": 0.0,
                "estimated_cost": 19.00
            }
        }


# ============================================
# HEALTH & ERROR MODELS
# ============================================

class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(
        ...,
        description="Service health status",
        examples=["healthy"]
    )
    service: str = Field(
        ...,
        description="Service name",
        examples=["YASEN-ALPHA SEC Event Intelligence API"]
    )
    version: str = Field(
        ...,
        description="Service version",
        examples=["1.0.0"]
    )
    environment: str = Field(
        ...,
        description="Current environment",
        examples=["production", "development"]
    )
    timestamp: str = Field(
        ...,
        description="Current timestamp",
        examples=["2024-01-15T10:30:00.123456"]
    )
    uptime: Optional[str] = Field(
        None,
        description="Service uptime",
        examples=["15d 3h 22m 45s"]
    )
    dependencies: Optional[Dict[str, bool]] = Field(
        None,
        description="Dependency health status",
        examples=[{"SEC EDGAR": True, "Cache": True}]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "YASEN-ALPHA SEC Event Intelligence API",
                "version": "1.0.0",
                "environment": "production",
                "timestamp": "2024-01-15T10:30:00.123456",
                "uptime": "15d 3h 22m 45s",
                "dependencies": {
                    "SEC EDGAR": True,
                    "Cache": True
                }
            }
        }


class ErrorResponse(BaseModelWithRequestId):
    """Error response model"""
    
    error: str = Field(
        ...,
        description="Error code",
        examples=["INVALID_QUERY", "RATE_LIMIT_EXCEEDED"]
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Invalid company query: XYZ"]
    )
    status_code: int = Field(
        ...,
        ge=100,
        le=599,
        description="HTTP status code",
        examples=[400]
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Error timestamp"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details",
        examples=[{"field": "query", "reason": "must be at least 1 character"}]
    )
    path: Optional[str] = Field(
        None,
        description="Request path",
        examples=["/api/v1/events"]
    )
    method: Optional[str] = Field(
        None,
        description="HTTP method",
        examples=["GET"]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "INVALID_QUERY",
                "message": "Invalid company query: XYZ",
                "status_code": 400,
                "timestamp": "2024-01-15T10:30:00.123456",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "details": {
                    "field": "query",
                    "reason": "must be at least 1 character"
                },
                "path": "/api/v1/events",
                "method": "GET"
            }
        }


# ============================================
# WEBHOOK MODELS (Future Enhancement)
# ============================================

class WebhookEvent(BaseModel):
    """Webhook event model"""
    
    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique webhook event ID"
    )
    event_type: EventType = Field(
        ...,
        description="Event type that triggered the webhook"
    )
    company_name: str = Field(
        ...,
        description="Company name",
        examples=["Apple Inc."]
    )
    ticker: Optional[str] = Field(
        None,
        description="Stock ticker"
    )
    filing_url: HttpUrl = Field(
        ...,
        description="URL to the filing"
    )
    event_data: Dict[str, Any] = Field(
        ...,
        description="Event data payload"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Event timestamp"
    )
    webhook_url: HttpUrl = Field(
        ...,
        description="Webhook destination URL"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts"
    )
    delivery_status: str = Field(
        default="pending",
        description="Delivery status",
        examples=["pending", "delivered", "failed"]
    )


class WebhookSubscription(BaseModel):
    """Webhook subscription model"""
    
    subscription_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique subscription ID"
    )
    webhook_url: HttpUrl = Field(
        ...,
        description="Webhook endpoint URL"
    )
    event_types: List[EventType] = Field(
        ...,
        description="Event types to subscribe to",
        min_length=1
    )
    company_filters: Optional[List[str]] = Field(
        None,
        description="Company filter (tickers or CIKs)",
        examples=[["AAPL", "MSFT"]]
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score"
    )
    active: bool = Field(
        default=True,
        description="Subscription active status"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp"
    )
    
    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate webhook URL"""
        # Ensure HTTPS in production
        if v.scheme != "https":
            # Allow HTTP for testing in development
            # In production, we would enforce HTTPS
            pass
        return v
    
    @model_validator(mode="after")
    def validate_subscription(self) -> "WebhookSubscription":
        """Validate subscription configuration"""
        if not self.event_types:
            raise ValueError("At least one event type is required")
        return self


# ============================================
# EXPORTS
# ============================================

__all__ = [
    # Enums
    "EventType",
    "FormType",
    "Tier",
    # Base Models
    "BaseModelWithTimestamps",
    "BaseModelWithRequestId",
    # SEC Models
    "SECFiling",
    "SECEvent",
    "CompanySearchResult",
    # Request Models
    "FilingEventRequest",
    "BatchEventRequest",
    # Response Models
    "EventResponse",
    "CompanySearchResponse",
    "FilingDetailsResponse",
    # Pricing Models
    "PricingTier",
    "PricingResponse",
    "UsageMetrics",
    # Health & Error Models
    "HealthResponse",
    "ErrorResponse",
    # Webhook Models
    "WebhookEvent",
    "WebhookSubscription",
]