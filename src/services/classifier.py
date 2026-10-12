"""
Event Classifier Service for SEC Event Intelligence API
========================================================

This module provides deterministic event classification for SEC filings.
It uses rule-based pattern matching to classify events from 8-K, 10-K, and 10-Q filings.

Key Features:
- Deterministic classification (no AI/LLM hallucinations)
- Rule-based pattern matching
- Evidence extraction with source citations
- Confidence scoring with multiple factors
- Rich fact extraction (dates, amounts, names, etc.)
- Support for 12+ major event types

Author: YASEN-ALPHA
Version: 2.2.0
License: Apache 2.0
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.models.schemas import EventType, SECEvent, SECFiling

# ============================================
# LOGGING SETUP
# ============================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================
# CLASSIFICATION RULES
# ============================================

class ClassificationRules:
    """
    Deterministic classification rules for SEC events.
    
    Each event type has:
    - Keywords: List of keywords/phrases that indicate this event
    - SEC items: List of SEC item numbers associated with this event
    - Patterns: Regex patterns for extracting specific data
    - Subtypes: Sub-categories within the event type
    - Confidence: Base confidence score for matches
    - Fact templates: Templates for extracting structured facts
    """
    
    # Cybersecurity events (SEC Item 1.05)
    CYBERSECURITY = {
        "keywords": [
            "cybersecurity", "cyber security", "data breach", "security breach",
            "unauthorized access", "cyber attack", "ransomware", "malware",
            "security incident", "cyber incident", "information security",
            "data security", "network intrusion", "system compromise",
            "phishing", "denial of service", "ddos", "security vulnerability"
        ],
        "sec_items": ["1.05"],
        "subtypes": {
            "breach": ["data breach", "security breach", "breach of security"],
            "incident": ["security incident", "cyber incident", "unauthorized access"],
            "investigation": ["investigation", "review", "assessment"],
            "remediation": ["remediation", "mitigation", "recovery", "restoration"]
        },
        "patterns": {
            "date": r"(?:on|about|approximately)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "impact": r"(?:impacted|affected|compromised)\s+(\d+)",
            "severity": r"(?:high|medium|low|critical|severe|minor)\s+(?:severity|risk|impact)",
            "systems_affected": r"(?:systems?|servers?|networks?|databases?)\s+(?:impacted|affected|compromised)",
            "data_types": r"(?:personal|financial|health|credit card|ssn|social security)\s+(?:data|information)"
        },
        "confidence": 0.90,
        "fact_templates": {
            "breach_date": "date",
            "systems_affected": "string",
            "data_types_compromised": "string",
            "severity": "string"
        }
    }
    
    # Acquisition events (SEC Item 1.01, 2.01)
    ACQUISITION = {
        "keywords": [
            "acquisition", "acquire", "merger", "merge", "consolidation",
            "purchase", "buy", "acquiring", "acquired", "combination",
            "transaction", "deal", "takeover", "tender offer",
            "letter of intent", "definitive agreement", "closing"
        ],
        "sec_items": ["1.01", "2.01"],
        "subtypes": {
            "asset_purchase": ["asset purchase", "purchase of assets", "assets"],
            "stock_purchase": ["stock purchase", "share purchase", "equity purchase"],
            "merger": ["merger", "merge", "combination", "consolidation"],
            "divestiture": ["divestiture", "divest", "sell", "disposition", "spin-off"]
        },
        "patterns": {
            "amount": r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "closing_date": r"(?:closing|closing date|effective date|completion)\s+(?:on|of|about)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "purchase_price": r"(?:purchase price|consideration|amount)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)",
            "target_company": r"(?:acquiring|purchase of|merger with)\s+([A-Z][a-zA-Z\s]+(?:Inc|Corp|LLC|Ltd|PLC))",
            "deal_value": r"(?:deal|transaction)\s+valued?\s+at\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)"
        },
        "confidence": 0.88,
        "fact_templates": {
            "acquisition_price": "money",
            "target_company": "string",
            "closing_date": "date",
            "deal_type": "string"
        }
    }
    
    # Auditor change events (SEC Item 4.01)
    AUDITOR_CHANGE = {
        "keywords": [
            "auditor", "accounting firm", "audit firm", "independent auditor",
            "auditor change", "change of auditor", "auditor dismissal",
            "auditor resignation", "auditor engagement", "new auditor",
            "previous auditor", "former auditor", "audit committee",
            "audit engagement", "audit services", "audit opinion"
        ],
        "sec_items": ["4.01"],
        "subtypes": {
            "dismissal": ["dismissal", "dismissed", "terminated", "fired"],
            "resignation": ["resignation", "resigned", "resign"],
            "engagement": ["engagement", "engaged", "appointed", "hired"],
            "disagreement": ["disagreement", "disagree", "dispute", "conflict"]
        },
        "patterns": {
            "auditor_name": r"(?:auditor|firm)\s+(?:is|was)\s+([A-Za-z\s]+(?:LLP|PLLC|CPA|PC|Inc\.|LLC))",
            "reason": r"(?:because|due to|reason for|in connection with)\s+([^.]+\\.)",
            "new_auditor": r"(?:new|appointed|engaged)\s+auditor\s+(?:is|will be)\s+([A-Za-z\s]+(?:LLP|PLLC|CPA|PC|Inc\.|LLC))",
            "previous_auditor": r"(?:previous|former|previously)\s+auditor\s+(?:was|is)\s+([A-Za-z\s]+(?:LLP|PLLC|CPA|PC|Inc\.|LLC))",
            "effective_date": r"(?:effective|effective date)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        },
        "confidence": 0.92,
        "fact_templates": {
            "new_auditor": "string",
            "previous_auditor": "string",
            "effective_date": "date",
            "reason": "string"
        }
    }
    
    # Executive change events (SEC Item 5.02)
    EXECUTIVE_CHANGE = {
        "keywords": [
            "ceo", "cfo", "coo", "cto", "cio", "cmo", "chief", "executive",
            "officer", "director", "president", "chairman", "board member",
            "appointment", "resignation", "departure", "retirement", "termination",
            "named executive", "management change", "executive compensation",
            "newly appointed", "replacement", "succession"
        ],
        "sec_items": ["5.02"],
        "subtypes": {
            "departure": ["resignation", "departure", "retirement", "termination", "separate"],
            "appointment": ["appointed", "appointment", "elected", "selected"],
            "compensation": ["compensation", "salary", "bonus", "equity award", "stock option"],
            "transition": ["transition", "interim", "acting", "temporary"]
        },
        "patterns": {
            "person_name": r"(?:appointed|resigned|departed|retired)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            "position": r"(?:as|to)\s+(?:the\s+)?(?:position\s+of\s+)?([A-Z]{2,4}O|Chief\s+[A-Za-z]+\s+Officer|Director|President|Chairman)",
            "effective_date": r"(?:effective|effective date|commencing)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "compensation_amount": r"(?:compensation|salary|bonus)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "years_at_company": r"(\d+)\s+years?\s+(?:with|at|of\s+service)",
            "new_position": r"(?:new|newly appointed|promoted to)\s+([A-Z]{2,4}O|Chief\s+[A-Za-z]+\s+Officer|Director|President|Chairman)"
        },
        "confidence": 0.90,
        "fact_templates": {
            "person_name": "string",
            "position": "string",
            "effective_date": "date",
            "compensation": "money",
            "years_of_service": "number"
        }
    }
    
    # Bankruptcy events (SEC Item 1.03, 2.03)
    BANKRUPTCY = {
        "keywords": [
            "bankruptcy", "chapter 7", "chapter 11", "chapter 13", "chapter 15",
            "insolvency", "insolvent", "liquidate", "liquidation", "reorganization",
            "receiver", "receivership", "trustee", "debtor", "creditor",
            "bankruptcy court", "filed for bankruptcy", "petition", "restructuring"
        ],
        "sec_items": ["1.03", "2.03"],
        "subtypes": {
            "chapter_11": ["chapter 11", "chapter eleven", "reorganization"],
            "chapter_7": ["chapter 7", "chapter seven", "liquidation"],
            "reorganization": ["reorganization", "restructuring", "rehabilitation"],
            "receivership": ["receivership", "receiver", "trustee"]
        },
        "patterns": {
            "chapter": r"chapter\s+(\d{1,2})",
            "court": r"(?:filed|petition)\s+(?:in|with)\s+the\s+([A-Za-z\s]+Bankruptcy Court)",
            "debt_amount": r"(?:debt|liabilities)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "asset_amount": r"(?:assets|property)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "filing_date": r"(?:filed|petitioned)\s+(?:on|about)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        },
        "confidence": 0.95,
        "fact_templates": {
            "chapter": "number",
            "debt_amount": "money",
            "asset_amount": "money",
            "filing_date": "date",
            "court": "string"
        }
    }
    
    # Risk factor updates (SEC Item 1A in 10-K/10-Q)
    RISK_FACTOR = {
        "keywords": [
            "risk factor", "risk", "uncertainty", "material risk",
            "potential risk", "business risk", "market risk", "financial risk",
            "operational risk", "strategic risk", "regulatory risk", "compliance risk",
            "risk disclosure", "risk management", "risk assessment"
        ],
        "sec_items": ["1A"],
        "subtypes": {
            "update": ["update", "updated", "revise", "revised", "amendment"],
            "new": ["new risk", "additional risk", "newly identified"],
            "removal": ["remove", "removed", "delete", "deleted"]
        },
        "patterns": {
            "risk_category": r"(?:risk factor|risks)\s+(?:related to|associated with)\s+([A-Za-z\s]+)",
            "severity": r"(?:may|could|could potentially)\s+(?:materially|significantly|adversely)\s+affect",
            "risk_description": r"(?:risk factor|risk of)\s+([^.]+\\.)"
        },
        "confidence": 0.85,
        "fact_templates": {
            "risk_category": "string",
            "risk_description": "string"
        }
    }
    
    # Financial statement changes (SEC Item 2.02, 9.01)
    FINANCIAL_STATEMENT = {
        "keywords": [
            "financial statement", "balance sheet", "income statement", "cash flow",
            "earnings", "revenue", "expense", "profit", "loss", "income",
            "financial results", "financial performance", "financial position",
            "revenue recognition", "accounting change", "accounting principle",
            "material weakness", "internal controls", "disclosure controls"
        ],
        "sec_items": ["2.02", "9.01"],
        "subtypes": {
            "restatement": ["restatement", "restate", "revised financials", "correction"],
            "amendment": ["amendment", "amend", "modify", "change"],
            "correction": ["correction", "correct", "adjust", "adjustment"]
        },
        "patterns": {
            "amount": r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "period": r"(?:for the|during the)\s+(?:quarter|year|fiscal)\s+(?:ended|ending)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            # FIXED: More specific revenue_amount pattern to avoid matching wrong numbers
            "revenue_amount": r"(?:revenue|sales)\s+(?:was|is|totaled)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)",
            "net_income": r"(?:net income|profit|earnings)\s+(?:was|is)\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "percentage_change": r"(?:increase|decrease|change)\s+of\s+([+-]?\d+(?:\.\d+)?)\s*%"
        },
        "confidence": 0.85,
        "fact_templates": {
            "revenue": "money",
            "net_income": "money",
            "period": "date",
            "percentage_change": "number"
        }
    }
    
    # Regulation changes (SEC Item 3.01, 3.02, 3.03)
    REGULATION = {
        "keywords": [
            "regulation", "regulatory", "compliance", "regulatory change",
            "new regulation", "regulatory requirement", "regulatory compliance",
            "government regulation", "law", "statute", "rule",
            "regulatory agency", "regulation amendment", "regulatory update"
        ],
        "sec_items": ["3.01", "3.02", "3.03"],
        "subtypes": {
            "new_regulation": ["new regulation", "new rule", "new law"],
            "change": ["change in regulation", "amendment", "modification"],
            "compliance": ["compliance requirement", "regulatory compliance"]
        },
        "patterns": {
            "regulation_name": r"(?:Regulation|Rule|Law)\s+([A-Za-z0-9\s\-]+)",
            "effective_date": r"(?:effective|becomes effective)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "regulatory_body": r"(?:SEC|FASB|PCAOB|FINRA|CFTC|Federal Reserve|FDIC|OCC)"
        },
        "confidence": 0.85,
        "fact_templates": {
            "regulation_name": "string",
            "effective_date": "date",
            "regulatory_body": "string"
        }
    }
    
    # ============================================
    # NEW EVENT TYPES
    # ============================================
    
    # Share Repurchase events (SEC Item 2.03, 3.02)
    SHARE_REPURCHASE = {
        "keywords": [
            "share repurchase", "stock buyback", "buyback", "repurchase",
            "share buyback", "stock repurchase", "repurchase program",
            "buyback program", "share repurchase program", "stock buyback program",
            "authorized share repurchase", "board authorized buyback",
            "repurchase of shares", "buyback of stock"
        ],
        "sec_items": ["2.03", "3.02"],
        "subtypes": {
            "authorization": ["authorized", "approve", "authorization", "approved"],
            "execution": ["executed", "completed", "repurchased", "bought back"],
            "program": ["program", "plan", "initiative", "authorization"]
        },
        "patterns": {
            "repurchase_amount": r"(?:repurchase|buyback|purchase)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "share_count": r"(\d+(?:,\d{3})*)\s+(?:shares|common stock)",
            "repurchase_price": r"(?:price|average price|per share)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)",
            "authorization_date": r"(?:authorized|approved)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "expiration_date": r"(?:expiring|through|until)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        },
        "confidence": 0.88,
        "fact_templates": {
            "repurchase_amount": "money",
            "share_count": "number",
            "repurchase_price": "money",
            "authorization_date": "date",
            "expiration_date": "date"
        }
    }
    
    # Debt Financing events (SEC Item 2.03)
    DEBT_FINANCING = {
        "keywords": [
            "debt", "financing", "loan", "borrow", "borrowing",
            "credit facility", "term loan", "revolving credit", "line of credit",
            "bond", "notes", "senior notes", "convertible notes",
            "debt offering", "bond offering", "debt issuance",
            "secured debt", "unsecured debt", "credit agreement",
            "debt financing", "capital raise", "debt capital"
        ],
        "sec_items": ["2.03"],
        "subtypes": {
            "bond_offering": ["bond", "notes", "debt offering", "bond offering"],
            "credit_facility": ["credit facility", "revolving credit", "term loan", "line of credit"],
            "loan": ["loan", "borrowing", "borrow"],
            "convertible_debt": ["convertible notes", "convertible debt", "exchangeable notes"]
        },
        "patterns": {
            "principal_amount": r"(?:principal|amount|total)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "interest_rate": r"(\d+(?:\.\d+)?)\s*%",
            "maturity_date": r"(?:mature|maturity|due)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "interest_rate_desc": r"(?:interest rate|rate)\s+of\s+(\d+(?:\.\d+)?)\s*%",
            "issuance_date": r"(?:issued|offered)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        },
        "confidence": 0.87,
        "fact_templates": {
            "principal_amount": "money",
            "interest_rate": "number",
            "maturity_date": "date",
            "issuance_date": "date",
            "debt_type": "string"
        }
    }
    
    # Dividend Announcement events (SEC Item 8.01, 5.07)
    DIVIDEND = {
        "keywords": [
            "dividend", "cash dividend", "stock dividend", "dividend declaration",
            "dividend payment", "quarterly dividend", "annual dividend",
            "dividend increase", "dividend decrease", "dividend suspension",
            "dividend announcement", "dividend declared", "dividend payable",
            "dividend per share", "dividend yield", "special dividend",
            "dividend policy", "dividend program"
        ],
        "sec_items": ["8.01", "5.07"],
        "subtypes": {
            "declaration": ["declared", "announce", "declaration", "announcement"],
            "increase": ["increase", "increased", "raise", "raised", "up"],
            "decrease": ["decrease", "decreased", "reduce", "reduced", "down"],
            "suspension": ["suspend", "suspended", "suspension", "stop", "halt"],
            "special": ["special dividend", "extra dividend", "one-time dividend"]
        },
        "patterns": {
            "dividend_amount": r"(?:dividend|payment)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s+(?:per share|per common share)",
            "ex_dividend_date": r"(?:ex-dividend|ex dividend)\s+(?:date|on)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "payment_date": r"(?:payable|payment)\s+(?:date|on)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "record_date": r"(?:record|record date|holder of record)\s+(?:date|on)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "declaration_date": r"(?:declared|announced)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "dividend_yield": r"(?:yield|dividend yield)\s+of\s+(\d+(?:\.\d+)?)\s*%"
        },
        "confidence": 0.90,
        "fact_templates": {
            "dividend_amount": "money",
            "ex_dividend_date": "date",
            "payment_date": "date",
            "record_date": "date",
            "declaration_date": "date",
            "dividend_yield": "number"
        }
    }
    
    # Litigation events (SEC Item 8.01)
    LITIGATION = {
        "keywords": [
            "litigation", "lawsuit", "suit", "legal proceeding", "legal action",
            "class action", "shareholder lawsuit", "investigation",
            "legal dispute", "arbitration", "mediation", "settlement",
            "judgment", "verdict", "appeal", "court ruling",
            "regulatory investigation", "government investigation",
            "enforcement action", "legal claim", "damages"
        ],
        "sec_items": ["8.01"],
        "subtypes": {
            "lawsuit": ["lawsuit", "suit", "legal action", "legal proceeding"],
            "settlement": ["settlement", "settled", "resolved", "resolution"],
            "investigation": ["investigation", "inquiry", "probe", "review"],
            "judgment": ["judgment", "verdict", "ruling", "decision", "order"],
            "class_action": ["class action", "class-action", "shareholder lawsuit"]
        },
        "patterns": {
            "plaintiff": r"(?:plaintiff|plaintiffs|complainant)\s+(?:is|are)\s+([A-Za-z\s]+)",
            "defendant": r"(?:defendant|defendants|respondent)\s+(?:is|are)\s+([A-Za-z\s]+)",
            "settlement_amount": r"(?:settlement|settled|agreed)\s+for\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "judgment_amount": r"(?:judgment|damages|award)\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "court_name": r"(?:in|before|pending in)\s+the\s+([A-Za-z\s]+Court)",
            "filing_date": r"(?:filed|commenced)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        },
        "confidence": 0.89,
        "fact_templates": {
            "plaintiff": "string",
            "defendant": "string",
            "settlement_amount": "money",
            "judgment_amount": "money",
            "court_name": "string",
            "filing_date": "date"
        }
    }
    
    # Map all rules by event type
    RULES = {
        EventType.CYBERSECURITY: CYBERSECURITY,
        EventType.ACQUISITION: ACQUISITION,
        EventType.AUDITOR_CHANGE: AUDITOR_CHANGE,
        EventType.EXECUTIVE_CHANGE: EXECUTIVE_CHANGE,
        EventType.BANKRUPTCY: BANKRUPTCY,
        EventType.RISK_FACTOR: RISK_FACTOR,
        EventType.FINANCIAL_STATEMENT: FINANCIAL_STATEMENT,
        EventType.REGULATION: REGULATION,
        # New event types
        EventType.SHARE_REPURCHASE: SHARE_REPURCHASE,
        EventType.DEBT_FINANCING: DEBT_FINANCING,
        EventType.DIVIDEND: DIVIDEND,
        EventType.LITIGATION: LITIGATION,
    }
    
    # SEC Item to Event Type mapping
    SEC_ITEM_MAP = {
        "1.01": EventType.ACQUISITION,
        "1.05": EventType.CYBERSECURITY,
        "1.03": EventType.BANKRUPTCY,
        "2.01": EventType.ACQUISITION,
        "2.02": EventType.FINANCIAL_STATEMENT,
        "2.03": EventType.BANKRUPTCY,
        "3.01": EventType.REGULATION,
        "3.02": EventType.REGULATION,
        "3.03": EventType.REGULATION,
        "4.01": EventType.AUDITOR_CHANGE,
        "5.02": EventType.EXECUTIVE_CHANGE,
        "1A": EventType.RISK_FACTOR,
        "9.01": EventType.FINANCIAL_STATEMENT,
        # New mappings
        "8.01": EventType.LITIGATION,  # Also used for dividends
        "5.07": EventType.DIVIDEND,
    }


# ============================================
# CLASSIFIER SERVICE
# ============================================

class EventClassifier:
    """
    Deterministic event classifier for SEC filings.
    
    This service uses rule-based pattern matching to classify events from SEC filings.
    All classification is deterministic - no AI/LLM used.
    """
    
    def __init__(self):
        """Initialize the classifier with rules and patterns."""
        self.rules = ClassificationRules.RULES
        self.sec_item_map = ClassificationRules.SEC_ITEM_MAP
        self._compile_patterns()
        
        logger.info(f"EventClassifier initialized with {len(self.rules)} event types")
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        self.compiled_patterns = {}
        
        for event_type, rule in self.rules.items():
            event_patterns = {}
            
            # Compile subtype patterns
            subtype_patterns = {}
            for subtype, keywords in rule.get("subtypes", {}).items():
                pattern = r"|".join(re.escape(kw) for kw in keywords)
                subtype_patterns[subtype] = re.compile(pattern, re.IGNORECASE)
            event_patterns["subtype_patterns"] = subtype_patterns
            
            # Compile keyword patterns
            keywords = rule.get("keywords", [])
            keyword_pattern = r"|".join(re.escape(kw) for kw in keywords)
            event_patterns["keyword_pattern"] = re.compile(keyword_pattern, re.IGNORECASE)
            
            # Compile extraction patterns
            extraction_patterns = {}
            for pattern_name, pattern_str in rule.get("patterns", {}).items():
                extraction_patterns[pattern_name] = re.compile(pattern_str, re.IGNORECASE)
            event_patterns["extraction_patterns"] = extraction_patterns
            
            self.compiled_patterns[event_type] = event_patterns
    
    def classify_filing(self, filing: SECFiling) -> List[SECEvent]:
        """Classify events from a filing."""
        events = []
        
        text = filing.source_text or ""
        if not text:
            logger.warning(f"No source text for filing {filing.accession_number}")
            return events
        
        # First pass: classify by SEC item
        sec_item_events = self._classify_by_sec_item(filing, text)
        events.extend(sec_item_events)
        
        # Second pass: classify by keyword matching
        keyword_events = self._classify_by_keywords(filing, text)
        events.extend(keyword_events)
        
        # Remove duplicates
        unique_events = self._deduplicate_events(events)
        
        # Enhance confidence
        enhanced_events = []
        for event in unique_events:
            enhanced_event = self._enhance_confidence(event, text)
            enhanced_events.append(enhanced_event)
        
        logger.info(
            f"Classified {len(enhanced_events)} events from filing {filing.accession_number}"
        )
        
        return enhanced_events
    
    def _classify_by_sec_item(self, filing: SECFiling, text: str) -> List[SECEvent]:
        """Classify events based on SEC item numbers."""
        events = []
        
        for sec_item in filing.items or []:
            event_type = self.sec_item_map.get(sec_item)
            if not event_type:
                continue
            
            rule = self.rules.get(event_type)
            if not rule:
                continue
            
            confidence = rule.get("confidence", 0.8) + 0.05
            
            event = self._create_event_from_rules(
                filing=filing,
                event_type=event_type,
                rule=rule,
                sec_item=sec_item,
                text=text,
                confidence=confidence
            )
            
            if event:
                events.append(event)
        
        return events
    
    def _classify_by_keywords(self, filing: SECFiling, text: str) -> List[SECEvent]:
        """Classify events based on keyword matching."""
        events = []
        text_lower = text.lower()
        
        for event_type, rule in self.rules.items():
            keywords = rule.get("keywords", [])
            matched_keywords = [kw for kw in keywords if kw.lower() in text_lower]
            
            if not matched_keywords:
                continue
            
            match_ratio = len(matched_keywords) / len(keywords) if keywords else 0
            
            sec_items = rule.get("sec_items", ["N/A"])
            
            for sec_item in sec_items:
                base_confidence = rule.get("confidence", 0.7)
                confidence = base_confidence * (0.7 + 0.3 * match_ratio)
                
                event = self._create_event_from_rules(
                    filing=filing,
                    event_type=event_type,
                    rule=rule,
                    sec_item=sec_item,
                    text=text,
                    confidence=confidence
                )
                
                if event:
                    events.append(event)
        
        return events
    
    def _create_event_from_rules(
        self,
        filing: SECFiling,
        event_type: EventType,
        rule: Dict[str, Any],
        sec_item: str,
        text: str,
        confidence: float
    ) -> Optional[SECEvent]:
        """Create an event from classification rules."""
        subtype = self._extract_subtype(text, rule)
        facts = self._extract_rich_facts(text, rule, event_type)
        event_date = self._extract_date(text, filing.filing_date)
        
        description = self._build_rich_description(
            event_type=event_type,
            subtype=subtype,
            company_name=filing.company_name,
            sec_item=sec_item,
            facts=facts
        )
        
        evidence = self._find_evidence(text, rule)
        
        enhanced_confidence = self._calculate_confidence(
            base_confidence=confidence,
            rule=rule,
            text=text,
            facts=facts,
            subtype=subtype
        )
        
        return SECEvent(
            event_type=event_type,
            event_subtype=subtype,
            sec_item=sec_item,
            date=event_date,
            description=description,
            company_name=filing.company_name,
            ticker=filing.ticker,
            cik=filing.company_cik,
            filing_url=filing.filing_url,
            source_text=evidence or "No specific evidence found",
            facts=facts,
            accession_number=filing.accession_number,
            confidence_score=enhanced_confidence,
            evidence_references=[{"text": evidence}] if evidence else []
        )
    
    def _extract_rich_facts(self, text: str, rule: Dict[str, Any], event_type: EventType) -> Dict[str, Any]:
        """Extract rich facts from text using patterns and templates."""
        facts = {}
        
        patterns = self.compiled_patterns.get(event_type, {}).get("extraction_patterns", {})
        
        for pattern_name, pattern in patterns.items():
            matches = pattern.findall(text)
            if matches:
                match = matches[0]
                if isinstance(match, tuple):
                    value = next((m for m in match if m), None)
                else:
                    value = match
                
                if value:
                    formatted_value = self._format_fact_value(pattern_name, value.strip())
                    if formatted_value is not None:
                        facts[pattern_name] = formatted_value
        
        fact_templates = rule.get("fact_templates", {})
        for fact_key, fact_type in fact_templates.items():
            if fact_key not in facts:
                alt_value = self._extract_alternative_fact(text, fact_key, fact_type)
                if alt_value is not None:
                    facts[fact_key] = alt_value
        
        # Deduplicate facts
        unique_facts = {}
        seen_values = set()
        for key, value in facts.items():
            if isinstance(value, (dict, list)):
                continue
            value_key = str(value)
            if value_key not in seen_values:
                unique_facts[key] = value
                seen_values.add(value_key)
        
        return unique_facts
    
    def _extract_alternative_fact(self, text: str, fact_key: str, fact_type: str) -> Optional[Any]:
        """Extract facts using alternative pattern matching."""
        alt_patterns = {
            "date": r"(?:on|about|approximately|effective as of)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "money": r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)",
            "string": r"([A-Z][a-zA-Z\s]+(?:Inc|Corp|LLC|Ltd|PLC|LLP|PLLC|CPA))",
            "number": r"(\d+(?:,\d{3})*)"
        }
        
        pattern = alt_patterns.get(fact_type)
        if not pattern:
            return None
        
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1) if match.groups() else match.group(0)
            return self._format_fact_value(fact_key, value.strip())
        
        return None
    
    def _format_fact_value(self, fact_key: str, value: str) -> Any:
        """Format fact value based on its type."""
        value = value.strip()
        
        # Skip CIK numbers
        if re.match(r"^\d{10}$", value):
            return None
        
        if "date" in fact_key or fact_key.endswith("_date"):
            try:
                from dateutil import parser
                parsed = parser.parse(value, fuzzy=True)
                return parsed.isoformat()
            except:
                return value
        
        if "amount" in fact_key or "price" in fact_key or "compensation" in fact_key:
            try:
                clean = value.replace("$", "").replace(",", "")
                if "million" in clean.lower():
                    clean = clean.replace("million", "").strip()
                    return float(clean) * 1_000_000
                elif "billion" in clean.lower():
                    clean = clean.replace("billion", "").strip()
                    return float(clean) * 1_000_000_000
                else:
                    return float(clean)
            except:
                return value
        
        if "percentage" in fact_key or "percent" in fact_key:
            try:
                clean = value.replace("%", "").strip()
                return float(clean)
            except:
                return value
        
        return value
    
    def _calculate_confidence(
        self,
        base_confidence: float,
        rule: Dict[str, Any],
        text: str,
        facts: Dict[str, Any],
        subtype: Optional[str]
    ) -> float:
        """Calculate enhanced confidence score."""
        confidence = base_confidence
        
        if len(facts) >= 3:
            confidence += 0.05
        elif len(facts) >= 2:
            confidence += 0.03
        
        if subtype:
            confidence += 0.03
        
        evidence = self._find_evidence(text, rule)
        if evidence and len(evidence) > 100:
            confidence += 0.02
        if evidence and len(evidence) < 20:
            confidence -= 0.03
        
        text_lower = text.lower()
        keywords = rule.get("keywords", [])
        matched_count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if keywords:
            match_ratio = matched_count / len(keywords)
            if match_ratio > 0.5:
                confidence += 0.02
            elif match_ratio < 0.2:
                confidence -= 0.03
        
        return min(max(confidence, 0.5), 0.98)
    
    def _enhance_confidence(self, event: SECEvent, text: str) -> SECEvent:
        """Enhance an existing event with better confidence scoring."""
        rule = self.rules.get(event.event_type)
        if not rule:
            return event
        
        enhanced_confidence = self._calculate_confidence(
            base_confidence=event.confidence_score,
            rule=rule,
            text=text,
            facts=event.facts,
            subtype=event.event_subtype
        )
        
        event.confidence_score = enhanced_confidence
        return event
    
    def _extract_subtype(self, text: str, rule: Dict[str, Any]) -> Optional[str]:
        """Extract event subtype from text."""
        subtypes = rule.get("subtypes", {})
        patterns = self.compiled_patterns.get(
            next((k for k, v in self.rules.items() if v == rule), EventType.OTHER),
            {}
        ).get("subtype_patterns", {})
        
        for subtype, pattern in patterns.items():
            if pattern.search(text):
                return subtype
        
        return None
    
    def _extract_date(self, text: str, default_date: datetime) -> str:
        """Extract date from text or use default."""
        date_patterns = [
            r"(?:on|about|approximately)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{1,2}/\d{1,2}/\d{4})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    from dateutil import parser
                    parsed = parser.parse(date_str, fuzzy=True)
                    return parsed.isoformat()
                except:
                    pass
        
        return default_date.isoformat()
    
    def _build_rich_description(
        self,
        event_type: EventType,
        subtype: Optional[str],
        company_name: str,
        sec_item: str,
        facts: Dict[str, Any]
    ) -> str:
        """Build rich event description with facts."""
        event_name = event_type.value.replace("_", " ").title()
        
        parts = [f"{company_name}: {event_name}"]
        
        if subtype:
            subtype_name = subtype.replace("_", " ").title()
            parts.append(subtype_name)
        
        fact_descriptions = []
        if "person_name" in facts:
            fact_descriptions.append(f"person: {facts['person_name']}")
        if "position" in facts:
            fact_descriptions.append(f"position: {facts['position']}")
        if "acquisition_price" in facts:
            amount = facts.get("acquisition_price")
            if amount:
                fact_descriptions.append(f"value: {amount}")
        elif "repurchase_amount" in facts:
            amount = facts.get("repurchase_amount")
            if amount:
                fact_descriptions.append(f"repurchase: {amount}")
        elif "dividend_amount" in facts:
            amount = facts.get("dividend_amount")
            if amount:
                fact_descriptions.append(f"dividend: {amount}")
        elif "principal_amount" in facts:
            amount = facts.get("principal_amount")
            if amount:
                fact_descriptions.append(f"debt: {amount}")
        elif "amount" in facts:
            amount = facts.get("amount")
            if amount:
                fact_descriptions.append(f"value: {amount}")
        if "severity" in facts:
            fact_descriptions.append(f"severity: {facts['severity']}")
        
        if fact_descriptions:
            parts.append(f"({', '.join(fact_descriptions)})")
        
        parts.append(f"(SEC Item {sec_item})")
        
        return " ".join(parts)
    
    def _find_evidence(self, text: str, rule: Dict[str, Any]) -> Optional[str]:
        """Find evidence text for the event."""
        keywords = rule.get("keywords", [])
        if not keywords:
            return None
        
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if any(kw.lower() in sentence.lower() for kw in keywords[:5]):
                if len(sentence) > 500:
                    return sentence[:500] + "..."
                return sentence
        
        paragraphs = text.split('\n\n')
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            if any(kw.lower() in paragraph.lower() for kw in keywords[:5]):
                if len(paragraph) > 500:
                    return paragraph[:500] + "..."
                return paragraph
        
        return None
    
    def _deduplicate_events(self, events: List[SECEvent]) -> List[SECEvent]:
        """Remove duplicate events, keeping the highest confidence."""
        grouped = {}
        
        for event in events:
            key = (event.event_type.value, event.sec_item, event.company_name)
            
            if key not in grouped:
                grouped[key] = event
            else:
                existing = grouped[key]
                if event.confidence_score > existing.confidence_score:
                    grouped[key] = event
        
        return sorted(grouped.values(), key=lambda e: e.confidence_score, reverse=True)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_event_type_from_sec_item(sec_item: str) -> Optional[EventType]:
    """Get event type from SEC item number."""
    return ClassificationRules.SEC_ITEM_MAP.get(sec_item)


def is_sec_item_related_to_event(sec_item: str, event_type: EventType) -> bool:
    """Check if an SEC item is related to an event type."""
    actual_type = get_event_type_from_sec_item(sec_item)
    return actual_type == event_type


def get_keywords_for_event_type(event_type: EventType) -> List[str]:
    """Get keywords for an event type."""
    rule = ClassificationRules.RULES.get(event_type)
    if rule:
        return rule.get("keywords", [])
    return []


# ============================================
# EXPORTS
# ============================================

__all__ = [
    "EventClassifier",
    "ClassificationRules",
    "get_event_type_from_sec_item",
    "is_sec_item_related_to_event",
    "get_keywords_for_event_type",
]
