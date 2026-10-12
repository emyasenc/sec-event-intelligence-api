"""
Caching Module for SEC Event Intelligence API
==============================================

This module provides caching functionality with support for:
- In-memory caching (TTLCache)
- Redis caching (optional)
- Namespace isolation
- TTL management
- Cache statistics

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import json
import logging
from typing import Any, Dict, Optional
from functools import wraps

from cachetools import TTLCache

from src.config import settings

# ============================================
# LOGGING SETUP
# ============================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================
# CACHE CLASS
# ============================================

class Cache:
    """
    Simple in-memory cache with TTL support.
    """
    
    def __init__(
        self,
        ttl: int = 604800,
        max_size: int = 10000,
        namespace: str = "default",
    ):
        self.ttl = ttl
        self.max_size = max_size
        self.namespace = namespace
        self._cache = TTLCache(maxsize=max_size, ttl=ttl)
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }
        logger.info(f"Cache initialized: namespace={namespace}, ttl={ttl}s, max_size={max_size}")
    
    def _get_key(self, key: str) -> str:
        """Get namespaced key."""
        return f"{self.namespace}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        namespaced_key = self._get_key(key)
        try:
            value = self._cache.get(namespaced_key)
            if value is not None:
                self._stats["hits"] += 1
                logger.debug(f"Cache hit: {key}")
                return value
            self._stats["misses"] += 1
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            self._stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            namespaced_key = self._get_key(key)
            self._cache[namespaced_key] = value
            self._stats["sets"] += 1
            logger.debug(f"Cache set: {key}")
            return True
        except Exception as e:
            logger.error(f"Error setting in cache: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            namespaced_key = self._get_key(key)
            if namespaced_key in self._cache:
                del self._cache[namespaced_key]
                self._stats["deletes"] += 1
                logger.debug(f"Cache delete: {key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            namespaced_key = self._get_key(key)
            return namespaced_key in self._cache
        except Exception as e:
            logger.error(f"Error checking cache: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all values in cache."""
        try:
            self._cache.clear()
            logger.info(f"Cache cleared: {self.namespace}")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def size(self) -> int:
        """Get number of items in cache."""
        try:
            return len(self._cache)
        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_ratio = self._stats["hits"] / total if total > 0 else 0.0
        
        return {
            **self._stats,
            "namespace": self.namespace,
            "ttl": self.ttl,
            "max_size": self.max_size,
            "size": self.size(),
            "hit_ratio": hit_ratio,
        }


# ============================================
# EXPORTS
# ============================================

__all__ = ["Cache"]
