"""
Security Module for SEC Event Intelligence API
==============================================

This module provides security utilities including:
- API key validation
- Security headers
- JWT token handling (future)

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import hashlib
import logging
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class APIKeyValidator:
    """
    API key validator for authentication.
    """
    
    def __init__(self):
        """Initialize the validator."""
        self._valid_keys = set()
        logger.info("APIKeyValidator initialized")
    
    async def validate_key(self, api_key: str) -> bool:
        """
        Validate an API key.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not api_key:
            return False
        
        # For development, accept test keys
        if settings.is_development:
            if api_key.startswith("test_"):
                return True
            if api_key.startswith("pro_"):
                return True
            if api_key.startswith("ultra_"):
                return True
            if api_key.startswith("mega_"):
                return True
            # In development, accept any key that's not empty
            return True
        
        # In production, validate against stored keys
        # This is a placeholder - in production, you'd check against a database
        if api_key in self._valid_keys:
            return True
        
        return False
    
    def add_valid_key(self, api_key: str) -> None:
        """
        Add a valid API key.
        
        Args:
            api_key: API key to add
        """
        self._valid_keys.add(api_key)
        logger.info(f"Added valid API key: {api_key[:8]}...")
    
    def remove_valid_key(self, api_key: str) -> None:
        """
        Remove a valid API key.
        
        Args:
            api_key: API key to remove
        """
        if api_key in self._valid_keys:
            self._valid_keys.remove(api_key)
            logger.info(f"Removed API key: {api_key[:8]}...")


class SecurityHeaders:
    """
    Security headers for HTTP responses.
    """
    
    def __init__(self):
        """Initialize security headers."""
        self.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        logger.info("SecurityHeaders initialized")
    
    def get_headers(self) -> dict:
        """
        Get security headers.
        
        Returns:
            Dictionary of security headers
        """
        return self.headers.copy()
    
    def add_header(self, key: str, value: str) -> None:
        """
        Add a custom security header.
        
        Args:
            key: Header name
            value: Header value
        """
        self.headers[key] = value


# ============================================
# EXPORTS
# ============================================

__all__ = ["APIKeyValidator", "SecurityHeaders"]
