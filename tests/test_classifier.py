"""Tests for event classifier."""

import pytest
from datetime import datetime
from src.services.classifier import EventClassifier
from src.models.schemas import SECFiling, FormType


def test_classifier_initialization():
    """Test classifier initializes with event types."""
    classifier = EventClassifier()
    assert classifier is not None
    assert len(classifier.rules) >= 8


def test_classify_cybersecurity_filing():
    """Test classification of cybersecurity event."""
    classifier = EventClassifier()
    
    filing = SECFiling(
        accession_number="test-001",
        form_type=FormType.FORM_8K,
        filing_date=datetime.now(),
        company_name="Test Corp",
        company_cik="0000000001",
        ticker="TEST",
        filing_url="https://example.com",
        document_url="https://example.com",
        source_text="The company reported a data breach affecting customers. "
                   "Unauthorized access was detected on January 15, 2026.",
    )
    
    events = classifier.classify_filing(filing)
    assert len(events) > 0
    # Should detect cybersecurity event
    assert any(e.event_type.value == "cybersecurity" for e in events)


def test_classify_auditor_change():
    """Test classification of auditor change."""
    classifier = EventClassifier()
    
    filing = SECFiling(
        accession_number="test-002",
        form_type=FormType.FORM_8K,
        filing_date=datetime.now(),
        company_name="Test Corp",
        company_cik="0000000001",
        ticker="TEST",
        filing_url="https://example.com",
        document_url="https://example.com",
        source_text="The company's independent auditor resigned effective immediately. "
                   "A new auditor has been engaged by the audit committee.",
    )
    
    events = classifier.classify_filing(filing)
    assert len(events) > 0
    assert any(e.event_type.value == "auditor_change" for e in events)
