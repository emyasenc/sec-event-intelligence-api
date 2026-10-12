"""
Fact Extractor Service for SEC Event Intelligence API
=======================================================

This module provides deterministic fact extraction from SEC filings using
rule-based pattern matching and structured data extraction.

Key Features:
- Extract dates, amounts, names, and other key facts
- Pattern-based extraction with regex
- Structured data output
- Confidence scoring for extracted facts
- Support for multiple fact types

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from src.models.schemas import SECEvent, SECFiling

# ============================================
# LOGGING SETUP
# ============================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================
# FACT EXTRACTION PATTERNS
# ============================================

class FactPatterns:
    """
    Comprehensive regex patterns for fact extraction from SEC filings.
    
    Each fact type has:
    - Pattern: Regex pattern for extraction
    - Type: Data type (str, int, float, date, money, etc.)
    - Confidence: Base confidence score
    - Validation: Optional validation function
    """
    
    # Date patterns
    DATES = {
        "date_iso": {
            "pattern": r"(\d{4}-\d{2}-\d{2})",
            "type": "date",
            "confidence": 0.95
        },
        "date_mdy": {
            "pattern": r"(\d{1,2}/\d{1,2}/\d{4})",
            "type": "date",
            "confidence": 0.90
        },
        "date_text": {
            "pattern": r"(?:on|about|approximately|effective as of)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "type": "date",
            "confidence": 0.85
        },
        "date_month_year": {
            "pattern": r"([A-Za-z]+\s+\d{4})",
            "type": "date",
            "confidence": 0.80
        },
        "date_quarter": {
            "pattern": r"(?:Q[1-4]\s+\d{4})",
            "type": "date",
            "confidence": 0.75
        }
    }
    
    # Monetary amounts
    MONEY = {
        "amount_usd": {
            "pattern": r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.95,
            "multiplier": {
                "million": 1_000_000,
                "billion": 1_000_000_000,
                "M": 1_000_000,
                "B": 1_000_000_000,
            }
        },
        "amount_usd_negative": {
            "pattern": r"\(?\$\s*([\d,]+(?:\.\d+)?)\)?",
            "type": "money",
            "confidence": 0.90
        },
        "amount_with_currency": {
            "pattern": r"([\d,]+(?:\.\d+)?)\s*(?:USD|EUR|GBP|JPY|CNY)",
            "type": "money",
            "confidence": 0.85
        }
    }
    
    # Percentages
    PERCENTAGES = {
        "percentage": {
            "pattern": r"(\d+(?:\.\d+)?)\s*%",
            "type": "percentage",
            "confidence": 0.95
        },
        "percentage_words": {
            "pattern": r"(?:about|approximately|around)\s+(\d+(?:\.\d+)?)\s*percent",
            "type": "percentage",
            "confidence": 0.85
        },
        "percentage_change": {
            "pattern": r"(?:increased|decreased|declined|rose|fell)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
            "type": "percentage",
            "confidence": 0.85
        }
    }
    
    # Names (people, companies, etc.)
    NAMES = {
        "person_name": {
            "pattern": r"(?:appointed|resigned|departed|retired|named|elected)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            "type": "name",
            "confidence": 0.85
        },
        "company_name": {
            "pattern": r"(?:acquisition of|purchase of|sale to|agreement with)\s+([A-Z][a-zA-Z\s]+(?:Inc|Corp|LLC|Ltd|PLC|S\\.A\\.))",
            "type": "name",
            "confidence": 0.80
        },
        "auditor_name": {
            "pattern": r"(?:auditor|firm)\s+(?:is|was)\s+([A-Za-z\s]+(?:LLP|PLLC|CPA|PC|Inc\\.|LLC))",
            "type": "name",
            "confidence": 0.90
        },
        "executive_name": {
            "pattern": r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:as|to)\s+(?:the\s+)?(?:position\s+of\s+)?(?:CEO|CFO|COO|CTO|CIO|CMO|Chief\s+[A-Za-z]+\s+Officer)",
            "type": "name",
            "confidence": 0.85
        }
    }
    
    # Numbers (counts, quantities, etc.)
    NUMBERS = {
        "integer": {
            "pattern": r"(\d{1,3}(?:,\d{3})*)(?:\s+(?:shares|units|employees|customers|users|members))",
            "type": "integer",
            "confidence": 0.90
        },
        "decimal": {
            "pattern": r"(\d+(?:\.\d+))(?:\s+(?:shares|units|employees|customers|users|members))",
            "type": "decimal",
            "confidence": 0.85
        },
        "count": {
            "pattern": r"(?:approximately|about|around)\s+(\d+(?:,\d{3})*)(?:\s+(?:shares|units|employees))",
            "type": "integer",
            "confidence": 0.80
        }
    }
    
    # Stock and share information
    STOCK = {
        "share_price": {
            "pattern": r"(?:trading at|price of|per share)\s+\$\s*([\d,]+(?:\.\d+)?)",
            "type": "money",
            "confidence": 0.90
        },
        "share_count": {
            "pattern": r"(\d+(?:,\d{3})*)\s+(?:shares|common stock|ordinary shares)",
            "type": "integer",
            "confidence": 0.90
        },
        "stock_exchange": {
            "pattern": r"(?:listed on|traded on|stock exchange)\s+(?:the\s+)?([A-Z]+)",
            "type": "string",
            "confidence": 0.85
        }
    }
    
    # Financial metrics
    FINANCIAL = {
        "revenue": {
            "pattern": r"(?:revenue|sales|turnover)\s+(?:was|is|totaled)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.95
        },
        "net_income": {
            "pattern": r"(?:net income|net loss|profit|earnings)\s+(?:was|is|totaled)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.95
        },
        "eps": {
            "pattern": r"(?:EPS|earnings per share)\s+(?:was|is)\s+\$\s*([\d,.]+)",
            "type": "money",
            "confidence": 0.90
        },
        "market_cap": {
            "pattern": r"(?:market cap|market capitalization)\s+(?:is|was|of)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.85
        },
        "debt": {
            "pattern": r"(?:debt|total debt|long-term debt)\s+(?:was|is|of)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.85
        },
        "cash": {
            "pattern": r"(?:cash|cash and cash equivalents)\s+(?:was|is|of)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.90
        }
    }
    
    # Risk and compliance
    RISK = {
        "risk_level": {
            "pattern": r"(?:high|medium|low|critical|severe|minor)\s+(?:risk|severity|impact)",
            "type": "string",
            "confidence": 0.70
        },
        "regulation_name": {
            "pattern": r"(?:Regulation|Rule|Law|Act)\s+([A-Za-z0-9\s\-]+(?:\s+of\s+\d{4})?)",
            "type": "string",
            "confidence": 0.80
        },
        "compliance_status": {
            "pattern": r"(?:compliant|non-compliant|in compliance|out of compliance|violation)",
            "type": "string",
            "confidence": 0.75
        }
    }
    
    # Acquisition and M&A
    M_AND_A = {
        "acquisition_price": {
            "pattern": r"(?:purchase price|consideration|amount|deal value)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.95
        },
        "closing_date": {
            "pattern": r"(?:closing|closing date|effective date|completion)\s+(?:on|of|about)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "type": "date",
            "confidence": 0.90
        },
        "acquisition_type": {
            "pattern": r"(?:asset purchase|stock purchase|merger|consolidation|divestiture|spin-off)",
            "type": "string",
            "confidence": 0.85
        }
    }
    
    # Employee and executive
    EMPLOYEE = {
        "employee_count": {
            "pattern": r"(\d+(?:,\d{3})*)\s+employees",
            "type": "integer",
            "confidence": 0.90
        },
        "executive_count": {
            "pattern": r"(\d+)\s+(?:executives|officers|directors)",
            "type": "integer",
            "confidence": 0.85
        },
        "compensation": {
            "pattern": r"(?:compensation|salary|bonus)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B|)",
            "type": "money",
            "confidence": 0.85
        }
    }
    
    # All patterns combined
    ALL_PATTERNS = {
        "dates": DATES,
        "money": MONEY,
        "percentages": PERCENTAGES,
        "names": NAMES,
        "numbers": NUMBERS,
        "stock": STOCK,
        "financial": FINANCIAL,
        "risk": RISK,
        "m_and_a": M_AND_A,
        "employee": EMPLOYEE,
    }


# ============================================
# EXTRACTOR SERVICE
# ============================================

class FactExtractor:
    """
    Deterministic fact extractor for SEC filings.
    
    This service extracts structured facts from SEC filing text using
    rule-based pattern matching and data validation.
    """
    
    def __init__(self):
        """Initialize the extractor with patterns."""
        self.patterns = FactPatterns.ALL_PATTERNS
        self._compiled_patterns = {}
        self._compile_patterns()
        
        logger.info("FactExtractor initialized with deterministic patterns")
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        for category, patterns in self.patterns.items():
            self._compiled_patterns[category] = {}
            for pattern_name, pattern_config in patterns.items():
                self._compiled_patterns[category][pattern_name] = {
                    "pattern": re.compile(pattern_config["pattern"], re.IGNORECASE | re.MULTILINE),
                    "type": pattern_config["type"],
                    "confidence": pattern_config["confidence"],
                    "multiplier": pattern_config.get("multiplier", {}),
                }
    
    def extract_facts(
        self,
        text: str,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract facts from text.
        
        Args:
            text: Text to extract facts from
            categories: Optional list of categories to extract
            
        Returns:
            Dictionary of extracted facts
        """
        if not text:
            return {}
        
        # If no categories specified, use all
        if not categories:
            categories = list(self.patterns.keys())
        
        # Extract facts from each category
        facts = {}
        for category in categories:
            if category in self._compiled_patterns:
                category_facts = self._extract_category_facts(text, category)
                if category_facts:
                    facts[category] = category_facts
        
        return facts
    
    def _extract_category_facts(self, text: str, category: str) -> Dict[str, Any]:
        """
        Extract facts from a specific category.
        
        Args:
            text: Text to extract from
            category: Category name
            
        Returns:
            Dictionary of extracted facts
        """
        category_facts = {}
        category_patterns = self._compiled_patterns.get(category, {})
        
        for pattern_name, pattern_config in category_patterns.items():
            pattern = pattern_config["pattern"]
            matches = pattern.findall(text)
            
            if matches:
                # Process matches
                processed_matches = []
                for match in matches:
                    if isinstance(match, tuple):
                        # Use the first non-empty group
                        value = next((m for m in match if m), match[0]) if match else None
                    else:
                        value = match
                    
                    if value:
                        # Process based on type
                        processed_value = self._process_value(
                            value=value,
                            value_type=pattern_config["type"],
                            pattern_config=pattern_config,
                            context=text
                        )
                        
                        if processed_value is not None:
                            processed_matches.append({
                                "value": processed_value,
                                "confidence": pattern_config["confidence"],
                                "raw": value,
                                "type": pattern_config["type"],
                            })
                
                if processed_matches:
                    # Store all matches
                    category_facts[pattern_name] = {
                        "matches": processed_matches,
                        "count": len(processed_matches),
                        "first": processed_matches[0] if processed_matches else None,
                        "last": processed_matches[-1] if processed_matches else None,
                    }
        
        return category_facts
    
    def _process_value(
        self,
        value: str,
        value_type: str,
        pattern_config: Dict[str, Any],
        context: str
    ) -> Any:
        """
        Process extracted value based on its type.
        
        Args:
            value: Raw extracted value
            value_type: Type of value (date, money, etc.)
            pattern_config: Pattern configuration
            context: Full text context
            
        Returns:
            Processed value
        """
        try:
            if value_type == "date":
                return self._process_date(value)
            elif value_type == "money":
                return self._process_money(value, pattern_config)
            elif value_type == "percentage":
                return self._process_percentage(value)
            elif value_type == "integer":
                return self._process_integer(value)
            elif value_type == "decimal":
                return self._process_decimal(value)
            elif value_type == "name":
                return self._process_name(value)
            elif value_type == "string":
                return value.strip()
            else:
                return value.strip()
        except Exception as e:
            logger.debug(f"Error processing value {value}: {str(e)}")
            return None
    
    def _process_date(self, value: str) -> Optional[str]:
        """
        Process date value.
        
        Args:
            value: Raw date string
            
        Returns:
            ISO formatted date or None
        """
        try:
            from dateutil import parser
            
            # Clean the value
            value = value.strip()
            
            # Try to parse with dateutil
            parsed = parser.parse(value, fuzzy=True)
            return parsed.isoformat()
        except:
            # Try common SEC date formats
            try:
                # MM/DD/YYYY
                if re.match(r"\d{1,2}/\d{1,2}/\d{4}", value):
                    parts = value.split("/")
                    return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                # Month DD, YYYY
                elif re.match(r"[A-Za-z]+\s+\d{1,2},?\s+\d{4}", value):
                    from dateutil import parser
                    parsed = parser.parse(value)
                    return parsed.isoformat()
            except:
                pass
            
            return None
    
    def _process_money(self, value: str, pattern_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process money value.
        
        Args:
            value: Raw money string
            pattern_config: Pattern configuration
            
        Returns:
            Money object with amount and metadata
        """
        try:
            # Clean the value
            value = value.strip().replace(",", "")
            
            # Parse the number
            if "million" in value.lower() or "billion" in value.lower():
                # Extract number and multiplier
                num_match = re.search(r"([\d,.]+)", value)
                if not num_match:
                    return None
                
                num = float(num_match.group(1).replace(",", ""))
                multiplier = 1
                
                if "billion" in value.lower() or "b" in value.lower():
                    multiplier = 1_000_000_000
                elif "million" in value.lower() or "m" in value.lower():
                    multiplier = 1_000_000
                
                amount = num * multiplier
            else:
                # Just a number
                amount = float(value.replace(",", ""))
            
            return {
                "amount": amount,
                "amount_str": f"${amount:,.2f}",
                "currency": "USD",
                "multiplier": multiplier if 'multiplier' in locals() else 1,
            }
        except:
            return None
    
    def _process_percentage(self, value: str) -> Optional[Dict[str, Any]]:
        """
        Process percentage value.
        
        Args:
            value: Raw percentage string
            
        Returns:
            Percentage object with value and metadata
        """
        try:
            value = value.strip().replace("%", "").replace(",", "")
            percentage = float(value)
            
            return {
                "percentage": percentage,
                "percentage_str": f"{percentage}%",
                "decimal": percentage / 100,
            }
        except:
            return None
    
    def _process_integer(self, value: str) -> Optional[int]:
        """
        Process integer value.
        
        Args:
            value: Raw integer string
            
        Returns:
            Integer or None
        """
        try:
            value = value.strip().replace(",", "")
            return int(float(value))
        except:
            return None
    
    def _process_decimal(self, value: str) -> Optional[float]:
        """
        Process decimal value.
        
        Args:
            value: Raw decimal string
            
        Returns:
            Float or None
        """
        try:
            value = value.strip().replace(",", "")
            return float(value)
        except:
            return None
    
    def _process_name(self, value: str) -> Optional[str]:
        """
        Process name value.
        
        Args:
            value: Raw name string
            
        Returns:
            Cleaned name or None
        """
        try:
            # Clean the name
            name = value.strip()
            
            # Remove extra whitespace
            name = re.sub(r'\s+', ' ', name)
            
            # Capitalize properly
            name = name.title()
            
            return name
        except:
            return None
    
    def extract_facts_from_filing(
        self,
        filing: SECFiling,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract facts from a filing.
        
        Args:
            filing: SEC filing
            categories: Optional list of categories to extract
            
        Returns:
            Dictionary of extracted facts
        """
        text = filing.source_text or ""
        if not text:
            logger.warning(f"No source text for filing {filing.accession_number}")
            return {}
        
        return self.extract_facts(text, categories)
    
    def extract_facts_from_events(
        self,
        events: List[SECEvent],
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract facts from a list of events.
        
        Args:
            events: List of SEC events
            categories: Optional list of categories to extract
            
        Returns:
            List of event facts
        """
        event_facts = []
        
        for event in events:
            facts = {
                "event_id": id(event),
                "event_type": event.event_type.value,
                "event_subtype": event.event_subtype,
                "company_name": event.company_name,
                "ticker": event.ticker,
                "extracted_facts": self.extract_facts(
                    event.source_text,
                    categories
                ),
                "confidence": event.confidence_score,
            }
            event_facts.append(facts)
        
        return event_facts
    
    def extract_specific_fact(
        self,
        text: str,
        fact_type: str,
        fact_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract a specific fact type from text.
        
        Args:
            text: Text to extract from
            fact_type: Fact category (e.g., "financial", "dates")
            fact_name: Fact name (e.g., "revenue", "date_iso")
            
        Returns:
            Extracted fact or None
        """
        if fact_type not in self._compiled_patterns:
            return None
        
        if fact_name not in self._compiled_patterns[fact_type]:
            return None
        
        pattern_config = self._compiled_patterns[fact_type][fact_name]
        pattern = pattern_config["pattern"]
        
        match = pattern.search(text)
        if not match:
            return None
        
        value = match.group(1) if match.groups() else match.group(0)
        
        processed_value = self._process_value(
            value=value,
            value_type=pattern_config["type"],
            pattern_config=pattern_config,
            context=text
        )
        
        if processed_value is None:
            return None
        
        return {
            "value": processed_value,
            "raw": value,
            "type": pattern_config["type"],
            "confidence": pattern_config["confidence"],
            "pattern": fact_name,
            "category": fact_type,
        }
    
    def extract_all_from_text(
        self,
        text: str,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract all facts from text with structured output.
        
        Args:
            text: Text to extract from
            categories: Optional list of categories to extract
            
        Returns:
            Structured facts with metadata
        """
        # Extract facts
        extracted_facts = self.extract_facts(text, categories)
        
        # Build structured output
        result = {
            "extracted": extracted_facts,
            "metadata": {
                "extracted_at": datetime.now().isoformat(),
                "text_length": len(text),
                "categories": categories or list(self.patterns.keys()),
                "total_facts": sum(
                    len(category_facts) 
                    for category_facts in extracted_facts.values()
                ),
            },
            "summary": self._build_summary(extracted_facts),
        }
        
        return result
    
    def _build_summary(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a summary of extracted facts.
        
        Args:
            facts: Extracted facts
            
        Returns:
            Summary dictionary
        """
        summary = {
            "total_categories": len(facts),
            "category_counts": {},
            "key_facts": {},
        }
        
        for category, category_facts in facts.items():
            count = len(category_facts)
            summary["category_counts"][category] = count
            
            # Extract key facts from each category
            for fact_name, fact_data in category_facts.items():
                if fact_data.get("first"):
                    first = fact_data["first"]
                    summary["key_facts"][f"{category}_{fact_name}"] = {
                        "value": first.get("value"),
                        "confidence": first.get("confidence"),
                        "type": first.get("type"),
                    }
        
        return summary


# ============================================
# HELPER FUNCTIONS
# ============================================

def extract_date(text: str) -> Optional[str]:
    """
    Extract a date from text.
    
    Args:
        text: Text to extract from
        
    Returns:
        ISO formatted date or None
    """
    extractor = FactExtractor()
    result = extractor.extract_specific_fact(text, "dates", "date_iso")
    
    if result:
        return result["value"]
    
    result = extractor.extract_specific_fact(text, "dates", "date_mdy")
    
    if result:
        return result["value"]
    
    result = extractor.extract_specific_fact(text, "dates", "date_text")
    
    if result:
        return result["value"]
    
    return None


def extract_money(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract money amount from text.
    
    Args:
        text: Text to extract from
        
    Returns:
        Money object or None
    """
    extractor = FactExtractor()
    result = extractor.extract_specific_fact(text, "money", "amount_usd")
    
    if result:
        return result["value"]
    
    result = extractor.extract_specific_fact(text, "money", "amount_usd_negative")
    
    if result:
        return result["value"]
    
    return None


def extract_percentage(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract percentage from text.
    
    Args:
        text: Text to extract from
        
    Returns:
        Percentage object or None
    """
    extractor = FactExtractor()
    result = extractor.extract_specific_fact(text, "percentages", "percentage")
    
    if result:
        return result["value"]
    
    return None


def extract_name(text: str) -> Optional[str]:
    """
    Extract a name from text.
    
    Args:
        text: Text to extract from
        
    Returns:
        Name or None
    """
    extractor = FactExtractor()
    
    # Try person name first
    result = extractor.extract_specific_fact(text, "names", "person_name")
    
    if result:
        return result["value"]
    
    # Try company name
    result = extractor.extract_specific_fact(text, "names", "company_name")
    
    if result:
        return result["value"]
    
    return None


# ============================================
# EXPORTS
# ============================================

__all__ = [
    "FactExtractor",
    "FactPatterns",
    "extract_date",
    "extract_money",
    "extract_percentage",
    "extract_name",
]