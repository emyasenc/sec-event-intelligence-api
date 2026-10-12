"""
Validation Utilities for SEC Event Intelligence API
====================================================

This module provides comprehensive validation and sanitization functions for
all API inputs, including:
- Company queries (name, ticker, CIK)
- Date ranges
- Form types
- Event types
- Pagination parameters
- Email and URL validation

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from src.models.schemas import EventType, FormType

# ============================================
# CONSTANTS
# ============================================

# Valid CIK patterns
CIK_PATTERN = re.compile(r"^\d{10}$")
CIK_PATTERN_WITH_LEADING = re.compile(r"^0*(\d{1,10})$")

# Ticker patterns
TICKER_PATTERN = re.compile(r"^[A-Za-z]{1,5}$")
TICKER_PATTERN_WITH_DOT = re.compile(r"^[A-Za-z]{1,5}\.[A-Za-z]{1,3}$")

# Company name patterns
COMPANY_NAME_MIN_LENGTH = 2
COMPANY_NAME_MAX_LENGTH = 255

# Date patterns
DATE_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MDY_PATTERN = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
DATE_MDY_SLASH_PATTERN = re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")

# Email pattern
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# URL pattern
URL_PATTERN = re.compile(
    r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/.*)?$"
)

# Pagination limits
MIN_LIMIT = 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 20

# Batch limits
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 50

# Confidence score limits
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


# ============================================
# COMPANY QUERY VALIDATION
# ============================================

def validate_company_query(query: str) -> Optional[str]:
    """
    Validate and clean a company query.
    
    Args:
        query: Company name, ticker, or CIK
        
    Returns:
        Cleaned query or None if invalid
    """
    if not query:
        return None
    
    # Trim whitespace
    query = query.strip()
    
    if not query:
        return None
    
    # Check length
    if len(query) < 1:
        return None
    
    if len(query) > 255:
        query = query[:255]
    
    # Remove any dangerous characters (basic sanitization)
    query = re.sub(r'[<>{}|\\^~\[\]`]', '', query)
    
    # If it looks like a CIK, normalize it
    if CIK_PATTERN.match(query):
        return query
    
    # If it looks like a ticker, uppercase it
    if TICKER_PATTERN.match(query):
        return query.upper()
    
    # If it looks like a ticker with exchange suffix
    if TICKER_PATTERN_WITH_DOT.match(query):
        return query.upper()
    
    # Otherwise, treat as company name
    return query


def is_valid_cik(cik: str) -> bool:
    """Check if a string is a valid CIK."""
    if not cik:
        return False
    
    cik = cik.strip()
    match = CIK_PATTERN_WITH_LEADING.match(cik)
    if not match:
        return False
    
    cik_clean = match.group(1)
    return 1 <= len(cik_clean) <= 10


def normalize_cik(cik: str) -> Optional[str]:
    """Normalize a CIK to 10 digits with leading zeros."""
    if not cik:
        return None
    
    cik = cik.strip()
    match = CIK_PATTERN_WITH_LEADING.match(cik)
    if not match:
        return None
    
    cik_clean = match.group(1)
    return cik_clean.zfill(10)


def is_valid_ticker(ticker: str) -> bool:
    """Check if a string is a valid ticker."""
    if not ticker:
        return False
    
    ticker = ticker.strip()
    
    if TICKER_PATTERN.match(ticker):
        return True
    
    if TICKER_PATTERN_WITH_DOT.match(ticker):
        return True
    
    return False


def normalize_ticker(ticker: str) -> Optional[str]:
    """Normalize a ticker to uppercase."""
    if not ticker:
        return None
    
    ticker = ticker.strip()
    
    if is_valid_ticker(ticker):
        return ticker.upper()
    
    return None


def is_valid_company_name(name: str) -> bool:
    """Check if a string is a valid company name."""
    if not name:
        return False
    
    name = name.strip()
    
    if len(name) < COMPANY_NAME_MIN_LENGTH:
        return False
    
    if len(name) > COMPANY_NAME_MAX_LENGTH:
        return False
    
    alphanumeric = sum(1 for c in name if c.isalnum())
    if alphanumeric < 1:
        return False
    
    return True


# ============================================
# DATE VALIDATION
# ============================================

def validate_date(date_str: str) -> Optional[datetime]:
    """Validate and parse a date string."""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Try ISO format (YYYY-MM-DD)
    if DATE_ISO_PATTERN.match(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass
    
    # Try MM/DD/YYYY
    if DATE_MDY_PATTERN.match(date_str):
        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            pass
    
    # Try MM-DD-YYYY
    if DATE_MDY_SLASH_PATTERN.match(date_str):
        try:
            return datetime.strptime(date_str, "%m-%d-%Y")
        except ValueError:
            pass
    
    return None


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Validate and parse a date range."""
    parsed_start = None
    parsed_end = None
    
    if start_date:
        parsed_start = validate_date(start_date)
        if not parsed_start:
            raise ValueError(f"Invalid start_date format: {start_date}")
    
    if end_date:
        parsed_end = validate_date(end_date)
        if not parsed_end:
            raise ValueError(f"Invalid end_date format: {end_date}")
    
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise ValueError("start_date must be before or equal to end_date")
    
    return parsed_start, parsed_end


# ============================================
# FORM TYPE VALIDATION
# ============================================

def validate_form_type(form_type: str) -> bool:
    """Check if a string is a valid SEC form type."""
    if not form_type:
        return False
    
    form_type = form_type.strip().upper()
    
    valid_forms = {
        "8-K", "10-K", "10-Q", "S-1", "S-3", "S-4",
        "DEF14A", "PRE14A", "SC 13G", "SC 13D", "144",
        "8K", "10K", "10Q", "S1", "S3", "S4",
    }
    
    if form_type in valid_forms:
        return True
    
    normalized = form_type.replace("-", "")
    if normalized in valid_forms:
        return True
    
    return False


def normalize_form_type(form_type: str) -> Optional[str]:
    """Normalize a form type to the standard format."""
    if not form_type:
        return None
    
    form_type = form_type.strip().upper()
    
    form_map = {
        "8K": "8-K",
        "10K": "10-K",
        "10Q": "10-Q",
        "S1": "S-1",
        "S3": "S-3",
        "S4": "S-4",
        "SC13G": "SC 13G",
        "SC13D": "SC 13D",
    }
    
    normalized = form_type.replace("-", "")
    if normalized in form_map:
        return form_map[normalized]
    
    return None


# ============================================
# EVENT TYPE VALIDATION
# ============================================

def validate_event_type(event_type: str) -> bool:
    """Check if a string is a valid event type."""
    if not event_type:
        return False
    
    event_type = event_type.strip().lower()
    
    valid_types = {
        "cybersecurity", "acquisition", "auditor_change", 
        "executive_change", "bankruptcy", "risk_factor",
        "financial_statement", "regulation", "other"
    }
    
    return event_type in valid_types


def normalize_event_type(event_type: str) -> Optional[str]:
    """Normalize an event type to the standard format."""
    if not event_type:
        return None
    
    event_type = event_type.strip().lower()
    
    event_map = {
        "cyber": "cybersecurity",
        "security": "cybersecurity",
        "breach": "cybersecurity",
        "acq": "acquisition",
        "merger": "acquisition",
        "audit": "auditor_change",
        "exec": "executive_change",
        "executive": "executive_change",
        "bank": "bankruptcy",
        "risk": "risk_factor",
        "financial": "financial_statement",
        "finance": "financial_statement",
        "reg": "regulation",
        "regulatory": "regulation",
    }
    
    if event_type in event_map:
        return event_map[event_type]
    
    return event_type if event_type in {"cybersecurity", "acquisition", "auditor_change", "executive_change", "bankruptcy", "risk_factor", "financial_statement", "regulation"} else None


# ============================================
# PAGINATION VALIDATION
# ============================================

def validate_limit(limit: int) -> int:
    """Validate and clamp a limit value."""
    if limit is None:
        return DEFAULT_LIMIT
    
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        return DEFAULT_LIMIT
    
    if limit < MIN_LIMIT:
        return MIN_LIMIT
    
    if limit > MAX_LIMIT:
        return MAX_LIMIT
    
    return limit


def validate_offset(offset: int) -> int:
    """Validate and clamp an offset value."""
    if offset is None:
        return 0
    
    try:
        offset = int(offset)
    except (ValueError, TypeError):
        return 0
    
    if offset < 0:
        return 0
    
    return offset


def validate_pagination(
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> Tuple[int, int]:
    """Validate pagination parameters."""
    return validate_limit(limit), validate_offset(offset)


# ============================================
# BATCH VALIDATION
# ============================================

def validate_batch_size(size: int) -> int:
    """Validate and clamp a batch size."""
    if size is None:
        return MIN_BATCH_SIZE
    
    try:
        size = int(size)
    except (ValueError, TypeError):
        return MIN_BATCH_SIZE
    
    if size < MIN_BATCH_SIZE:
        return MIN_BATCH_SIZE
    
    if size > MAX_BATCH_SIZE:
        return MAX_BATCH_SIZE
    
    return size


def validate_batch_queries(queries: List[str]) -> List[str]:
    """Validate and clean a list of batch queries."""
    if not queries:
        raise ValueError("Batch queries cannot be empty")
    
    if len(queries) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Batch size {len(queries)} exceeds maximum of {MAX_BATCH_SIZE}"
        )
    
    cleaned_queries = []
    seen = set()
    
    for query in queries:
        if not query:
            continue
        
        cleaned = validate_company_query(query)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            cleaned_queries.append(cleaned)
    
    if not cleaned_queries:
        raise ValueError("No valid queries in batch")
    
    return cleaned_queries


# ============================================
# CONFIDENCE SCORE VALIDATION
# ============================================

def validate_confidence(score: float) -> float:
    """Validate and clamp a confidence score."""
    if score is None:
        return 0.0
    
    try:
        score = float(score)
    except (ValueError, TypeError):
        return 0.0
    
    if score < MIN_CONFIDENCE:
        return MIN_CONFIDENCE
    
    if score > MAX_CONFIDENCE:
        return MAX_CONFIDENCE
    
    return score


# ============================================
# EMAIL & URL VALIDATION
# ============================================

def validate_email(email: str) -> bool:
    """Validate an email address."""
    if not email:
        return False
    
    email = email.strip()
    
    if len(email) > 254:
        return False
    
    return bool(EMAIL_PATTERN.match(email))


def validate_url(url: str) -> bool:
    """Validate a URL."""
    if not url:
        return False
    
    url = url.strip()
    
    if len(url) > 2048:
        return False
    
    if not URL_PATTERN.match(url):
        return False
    
    return True


# ============================================
# STRING SANITIZATION
# ============================================

def sanitize_string(value: str) -> str:
    """Sanitize a string by removing dangerous characters."""
    if not value:
        return ""
    
    value = re.sub(r'<[^>]+>', '', value)
    value = re.sub(r'[<>{}|\\^~\[\]`;]', '', value)
    value = re.sub(r'\s+', ' ', value)
    
    return value.strip()


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Sanitize text for output."""
    if not text:
        return ""
    
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()


# ============================================
# COMPOSITE VALIDATORS
# ============================================

def validate_all_inputs(
    query: Optional[str] = None,
    form_type: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate all common input parameters."""
    result = {}
    
    if query is not None:
        validated_query = validate_company_query(query)
        if not validated_query:
            raise ValueError(f"Invalid query: {query}")
        result["query"] = validated_query
    
    if form_type is not None:
        if not validate_form_type(form_type):
            raise ValueError(f"Invalid form_type: {form_type}")
        result["form_type"] = normalize_form_type(form_type)
    
    if event_type is not None:
        if not validate_event_type(event_type):
            raise ValueError(f"Invalid event_type: {event_type}")
        result["event_type"] = normalize_event_type(event_type)
    
    if limit is not None:
        result["limit"] = validate_limit(limit)
    
    if start_date or end_date:
        parsed_start, parsed_end = validate_date_range(start_date, end_date)
        if parsed_start:
            result["start_date"] = parsed_start
        if parsed_end:
            result["end_date"] = parsed_end
    
    return result


# ============================================
# EXPORTS
# ============================================

__all__ = [
    "validate_company_query",
    "is_valid_cik",
    "normalize_cik",
    "is_valid_ticker",
    "normalize_ticker",
    "is_valid_company_name",
    "validate_date",
    "validate_date_range",
    "validate_form_type",
    "normalize_form_type",
    "validate_event_type",
    "normalize_event_type",
    "validate_limit",
    "validate_offset",
    "validate_pagination",
    "validate_batch_size",
    "validate_batch_queries",
    "validate_confidence",
    "validate_email",
    "validate_url",
    "sanitize_string",
    "sanitize_text",
    "validate_all_inputs",
    "MIN_LIMIT",
    "MAX_LIMIT",
    "DEFAULT_LIMIT",
    "MIN_BATCH_SIZE",
    "MAX_BATCH_SIZE",
    "MIN_CONFIDENCE",
    "MAX_CONFIDENCE",
]
