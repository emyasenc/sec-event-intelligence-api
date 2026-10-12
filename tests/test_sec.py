"""Tests for SEC EDGAR client."""

import pytest
from src.services.sec import SECService


def test_sec_service_initialization():
    """Test SEC service initializes correctly."""
    service = SECService()
    assert service is not None
    assert service.client is not None


@pytest.mark.asyncio
async def test_search_company_by_ticker():
    """Test searching for a company by ticker."""
    service = SECService()
    result = await service.search_company("AAPL")
    assert result is not None
    assert result["ticker"] == "AAPL"
    assert result["cik"] == "0000320193"


@pytest.mark.asyncio
async def test_search_company_by_cik():
    """Test searching for a company by CIK."""
    service = SECService()
    result = await service.search_company("0000320193")
    assert result is not None
