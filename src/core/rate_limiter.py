"""
Rate Limiter Module for SEC Event Intelligence API
===================================================

This module provides rate limiting functionality with support for:
- In-memory rate limiting
- Tier-based limits
- Soft and hard limits
- Usage tracking

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from collections import defaultdict

from src.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RateLimiter:
    """
    Simple in-memory rate limiter with tier support.
    """
    
    def __init__(self):
        """Initialize the rate limiter."""
        self._requests: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "reset_at": time.time() + 60,
        })
        self._stats = {
            "total_requests": 0,
            "blocked_requests": 0,
        }
        logger.info("RateLimiter initialized")
    
    def check_rate_limit(
        self,
        client_id: str,
        limit: int,
        window: int = 60
    ) -> Tuple[bool, int, Optional[datetime]]:
        """
        Check if a request is allowed under rate limits.
        
        Args:
            client_id: Client identifier
            limit: Maximum requests per window
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        now = time.time()
        
        # Get or create client record
        client_record = self._requests[client_id]
        
        # Check if window has expired
        if client_record["reset_at"] < now:
            # Reset the window
            client_record["count"] = 0
            client_record["reset_at"] = now + window
        
        # Check if limit is exceeded
        is_allowed = client_record["count"] < limit
        
        if is_allowed:
            client_record["count"] += 1
            self._stats["total_requests"] += 1
        else:
            self._stats["blocked_requests"] += 1
        
        remaining = max(0, limit - client_record["count"])
        reset_time = datetime.fromtimestamp(client_record["reset_at"])
        
        return is_allowed, remaining, reset_time
    
    def check_rate_limit_with_stats(
        self,
        client_id: str,
        limit: int,
        window: int = 60
    ) -> Tuple[bool, int, Optional[datetime], float]:
        """
        Check rate limit with additional statistics.
        
        Args:
            client_id: Client identifier
            limit: Maximum requests per window
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time, usage_percentage)
        """
        now = time.time()
        
        # Get or create client record
        client_record = self._requests[client_id]
        
        # Check if window has expired
        if client_record["reset_at"] < now:
            client_record["count"] = 0
            client_record["reset_at"] = now + window
        
        # Calculate usage percentage
        usage_percentage = (client_record["count"] / limit) * 100 if limit > 0 else 0
        
        # Check if limit is exceeded
        is_allowed = client_record["count"] < limit
        
        if is_allowed:
            client_record["count"] += 1
            self._stats["total_requests"] += 1
        else:
            self._stats["blocked_requests"] += 1
        
        remaining = max(0, limit - client_record["count"])
        reset_time = datetime.fromtimestamp(client_record["reset_at"])
        
        return is_allowed, remaining, reset_time, usage_percentage
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            **self._stats,
            "active_clients": len(self._requests),
            "timestamp": datetime.now().isoformat(),
        }
    
    def reset_client(self, client_id: str) -> None:
        """
        Reset a client's rate limit.
        
        Args:
            client_id: Client identifier
        """
        if client_id in self._requests:
            del self._requests[client_id]
            logger.info(f"Reset rate limit for client: {client_id}")
    
    def reset_all(self) -> None:
        """Reset all rate limits."""
        self._requests.clear()
        self._stats = {
            "total_requests": 0,
            "blocked_requests": 0,
        }
        logger.info("Reset all rate limits")


# ============================================
# EXPORTS
# ============================================

__all__ = ["RateLimiter"]
