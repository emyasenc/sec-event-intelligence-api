"""
Company Enricher Service for SEC Event Intelligence API
========================================================

This module provides company enrichment functionality, aggregating data from
multiple sources to provide comprehensive company information.

Key Features:
- Company data enrichment from multiple sources
- Industry classification (SIC, NAICS)
- Stock exchange information
- Company metadata aggregation
- Caching for performance
- Fallback mechanisms for data sources

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from cachetools import TTLCache

from src.models.schemas import CompanySearchResult

# ============================================
# LOGGING SETUP
# ============================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================
# CONSTANTS & MAPPINGS
# ============================================

# SIC Code to Industry Mapping
SIC_TO_INDUSTRY = {
    "7370": "Computer Programming, Data Processing",
    "7371": "Computer Programming Services",
    "7372": "Prepackaged Software",
    "7373": "Computer Integrated Systems Design",
    "7374": "Computer Processing and Data Preparation",
    "7375": "Information Retrieval Services",
    "7376": "Computer Facilities Management Services",
    "7377": "Computer Rental and Leasing",
    "7378": "Computer Maintenance and Repair",
    "7379": "Computer Related Services, Not Elsewhere Classified",
    "3570": "Computer and Office Equipment",
    "3571": "Electronic Computers",
    "3572": "Computer Storage Devices",
    "3575": "Computer Terminals",
    "3576": "Computer Communication Equipment",
    "3577": "Computer Peripheral Equipment, Not Elsewhere Classified",
    "3578": "Calculating and Accounting Machines",
    "3579": "Office Machines, Not Elsewhere Classified",
    "3661": "Telephone and Telegraph Apparatus",
    "3663": "Radio and Television Broadcasting and Communications Equipment",
    "3669": "Communications Equipment, Not Elsewhere Classified",
    "3670": "Electronic Components and Accessories",
    "3671": "Electron Tubes",
    "3672": "Printed Circuit Boards",
    "3674": "Semiconductors and Related Devices",
    "3675": "Electronic Capacitors",
    "3676": "Electronic Resistors",
    "3677": "Electronic Coils, Transformers, and Other Inductors",
    "3678": "Electronic Connectors",
    "3679": "Electronic Components, Not Elsewhere Classified",
    "2834": "Pharmaceutical Preparations",
    "2835": "In Vitro and In Vivo Diagnostic Substances",
    "2836": "Biological Products, Except Diagnostic Substances",
    "8090": "Miscellaneous Health and Allied Services, Not Elsewhere Classified",
    "8092": "Medical Laboratories",
    "8093": "Specialty Outpatient Facilities, Not Elsewhere Classified",
    "8099": "Health and Allied Services, Not Elsewhere Classified",
}

# SIC Code to Sector Mapping
SIC_TO_SECTOR = {
    "7370": "Technology",
    "7371": "Technology",
    "7372": "Technology",
    "7373": "Technology",
    "7374": "Technology",
    "7375": "Technology",
    "7376": "Technology",
    "7377": "Technology",
    "7378": "Technology",
    "7379": "Technology",
    "3570": "Technology",
    "3571": "Technology",
    "3572": "Technology",
    "3575": "Technology",
    "3576": "Technology",
    "3577": "Technology",
    "3578": "Technology",
    "3579": "Technology",
    "3661": "Technology",
    "3663": "Technology",
    "3669": "Technology",
    "3670": "Technology",
    "3671": "Technology",
    "3672": "Technology",
    "3674": "Technology",
    "3675": "Technology",
    "3676": "Technology",
    "3677": "Technology",
    "3678": "Technology",
    "3679": "Technology",
    "2834": "Healthcare",
    "2835": "Healthcare",
    "2836": "Healthcare",
    "8090": "Healthcare",
    "8092": "Healthcare",
    "8093": "Healthcare",
    "8099": "Healthcare",
}

# Exchange to Country Mapping
EXCHANGE_COUNTRY = {
    "NASDAQ": "United States",
    "NYSE": "United States",
    "NYSE ARCA": "United States",
    "NYSE MKT": "United States",
    "CBOE": "United States",
    "BATS": "United States",
    "LSE": "United Kingdom",
    "TSE": "Japan",
    "HKEX": "Hong Kong",
    "SSE": "China",
    "SZSE": "China",
    "TSX": "Canada",
    "ASX": "Australia",
    "DAX": "Germany",
    "CAC": "France",
    "FTSE": "United Kingdom",
}

# Exchange to Currency Mapping
EXCHANGE_CURRENCY = {
    "NASDAQ": "USD",
    "NYSE": "USD",
    "NYSE ARCA": "USD",
    "NYSE MKT": "USD",
    "CBOE": "USD",
    "BATS": "USD",
    "LSE": "GBP",
    "TSE": "JPY",
    "HKEX": "HKD",
    "SSE": "CNY",
    "SZSE": "CNY",
    "TSX": "CAD",
    "ASX": "AUD",
    "DAX": "EUR",
    "CAC": "EUR",
    "FTSE": "GBP",
}


# ============================================
# ENRICHER SERVICE
# ============================================

class CompanyEnricher:
    """
    Company enrichment service that aggregates data from multiple sources.
    
    This service enriches company information with:
    - Industry classification
    - Sector information
    - Stock exchange details
    - Company metadata
    """
    
    def __init__(self):
        """Initialize the enricher with caching."""
        self.cache = TTLCache(maxsize=1000, ttl=86400)  # 24 hour cache
        logger.info("CompanyEnricher initialized")
    
    def enrich_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich company data with additional information.
        
        Args:
            company_data: Basic company data (name, ticker, cik, etc.)
            
        Returns:
            Enriched company data
        """
        try:
            # Extract key identifiers
            cik = company_data.get("cik", "")
            ticker = company_data.get("ticker", "").upper() if company_data.get("ticker") else ""
            name = company_data.get("name", "")
            
            # Check cache
            cache_key = f"enrich_{cik}_{ticker}_{name[:20]}"
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for company: {name}")
                return cached_result
            
            # Start with the original data
            enriched = company_data.copy()
            
            # Add industry information
            sic_code = company_data.get("sic_code")
            if sic_code:
                enriched["industry"] = SIC_TO_INDUSTRY.get(sic_code, company_data.get("industry"))
                enriched["sector"] = SIC_TO_SECTOR.get(sic_code, company_data.get("sector"))
            
            # Add exchange information
            exchange = company_data.get("exchange")
            if exchange:
                enriched["exchange_country"] = EXCHANGE_COUNTRY.get(exchange, "Unknown")
                enriched["currency"] = EXCHANGE_CURRENCY.get(exchange, "USD")
            else:
                # Try to determine exchange from ticker
                if ticker:
                    exchange = self._determine_exchange(ticker)
                    if exchange:
                        enriched["exchange"] = exchange
                        enriched["exchange_country"] = EXCHANGE_COUNTRY.get(exchange, "Unknown")
                        enriched["currency"] = EXCHANGE_CURRENCY.get(exchange, "USD")
            
            # Add enrichment metadata
            enriched["enriched_at"] = datetime.now().isoformat()
            enriched["enrichment_sources"] = ["SIC Mapping", "Exchange Mapping"]
            
            # Cache the result
            self.cache[cache_key] = enriched
            
            logger.info(f"Enriched company: {name} ({ticker})")
            return enriched
            
        except Exception as e:
            logger.error(f"Error enriching company {company_data.get('name')}: {str(e)}")
            # Return original data on error
            return company_data
    
    def _determine_exchange(self, ticker: str) -> Optional[str]:
        """
        Determine primary exchange based on ticker patterns.
        
        Args:
            ticker: Stock ticker
            
        Returns:
            Exchange name or None
        """
        ticker = ticker.upper()
        
        # Pattern-based exchange detection
        if ticker.endswith(".L"):
            return "LSE"
        elif ticker.endswith(".T"):
            return "TSE"
        elif ticker.endswith(".HK"):
            return "HKEX"
        elif ticker.endswith(".SS") or ticker.endswith(".SHA"):
            return "SSE"
        elif ticker.endswith(".SZ") or ticker.endswith(".SHE"):
            return "SZSE"
        elif ticker.endswith(".TO"):
            return "TSX"
        elif ticker.endswith(".AX"):
            return "ASX"
        elif ticker.endswith(".DE"):
            return "DAX"
        elif ticker.endswith(".PA"):
            return "CAC"
        elif ticker.endswith(".LN"):
            return "LSE"
        
        # US exchanges
        if len(ticker) <= 4 and ticker.isalpha():
            return "NASDAQ"
        elif ticker.isalpha():
            return "NYSE"
        
        return None
    
    def get_industry_from_sic(self, sic_code: str) -> Optional[str]:
        """Get industry from SIC code."""
        return SIC_TO_INDUSTRY.get(sic_code)
    
    def get_sector_from_sic(self, sic_code: str) -> Optional[str]:
        """Get sector from SIC code."""
        return SIC_TO_SECTOR.get(sic_code)
    
    def get_exchange_country(self, exchange: str) -> str:
        """Get country for an exchange."""
        return EXCHANGE_COUNTRY.get(exchange, "Unknown")
    
    def get_exchange_currency(self, exchange: str) -> str:
        """Get currency for an exchange."""
        return EXCHANGE_CURRENCY.get(exchange, "USD")
    
    def format_response(self, enriched: Dict[str, Any]) -> CompanySearchResult:
        """
        Format enriched data as CompanySearchResult.
        
        Args:
            enriched: Enriched company data
            
        Returns:
            CompanySearchResult
        """
        return CompanySearchResult(
            name=enriched.get("name", ""),
            ticker=enriched.get("ticker"),
            cik=enriched.get("cik", ""),
            sic_code=enriched.get("sic_code"),
            industry=enriched.get("industry"),
            exchange=enriched.get("exchange"),
            sector=enriched.get("sector"),
            headquarters=enriched.get("headquarters"),
            founded_year=enriched.get("founded_year"),
            website=enriched.get("website"),
            description=enriched.get("description"),
            recent_filings=enriched.get("recent_filings"),
            confidence_score=enriched.get("confidence_score", 1.0),
        )


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_industry_for_sic(sic_code: str) -> Optional[str]:
    """Get industry for SIC code."""
    return SIC_TO_INDUSTRY.get(sic_code)


def get_sector_for_sic(sic_code: str) -> Optional[str]:
    """Get sector for SIC code."""
    return SIC_TO_SECTOR.get(sic_code)


def get_industries() -> Dict[str, str]:
    """Get all SIC to industry mappings."""
    return SIC_TO_INDUSTRY.copy()


def get_sectors() -> Dict[str, str]:
    """Get all SIC to sector mappings."""
    return SIC_TO_SECTOR.copy()


def get_exchanges() -> Dict[str, Dict[str, str]]:
    """Get all exchange information."""
    exchanges = {}
    for exchange in set(list(EXCHANGE_COUNTRY.keys()) + list(EXCHANGE_CURRENCY.keys())):
        exchanges[exchange] = {
            "country": EXCHANGE_COUNTRY.get(exchange, "Unknown"),
            "currency": EXCHANGE_CURRENCY.get(exchange, "Unknown"),
        }
    return exchanges


# ============================================
# EXPORTS
# ============================================

__all__ = [
    "CompanyEnricher",
    "get_industry_for_sic",
    "get_sector_for_sic",
    "get_industries",
    "get_sectors",
    "get_exchanges",
]
