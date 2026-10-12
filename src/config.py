"""
Configuration Module for SEC Event Intelligence API
====================================================

This module provides application configuration management using Pydantic
settings with environment variable support.

Key Features:
- Environment variable loading
- Validation of all settings
- Production/development modes
- Rate limiting configuration
- SEC EDGAR API settings
- Cache configuration
- Logging configuration

Author: YASEN-ALPHA
Version: 1.0.0
License: Apache 2.0
"""

import logging
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings

# ============================================
# PATHS
# ============================================

# Get the root directory
ROOT_DIR = Path(__file__).parent.parent
ENV_FILE = ROOT_DIR / ".env"


# ============================================
# ENUMS
# ============================================

class Environment(str, Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================================
# NESTED CONFIGURATION MODELS
# ============================================

class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    
    free: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Rate limit for free tier (requests per minute)"
    )
    pro: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Rate limit for Pro tier (requests per minute)"
    )
    ultra: int = Field(
        default=40,
        ge=1,
        le=1000,
        description="Rate limit for Ultra tier (requests per minute)"
    )
    mega: int = Field(
        default=60,
        ge=1,
        le=5000,
        description="Rate limit for Mega tier (requests per minute)"
    )
    window: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Rate limit window in seconds"
    )
    soft_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Soft limit threshold (percentage of limit)"
    )


class PricingConfig(BaseModel):
    """Pricing configuration"""
    
    free_requests: int = Field(
        default=500,
        ge=0,
        description="Free tier requests per month"
    )
    pro_requests: int = Field(
        default=10000,
        ge=0,
        description="Pro tier requests per month"
    )
    pro_price: int = Field(
        default=25,
        ge=0,
        description="Pro tier monthly price in USD"
    )
    ultra_requests: int = Field(
        default=50000,
        ge=0,
        description="Ultra tier requests per month"
    )
    ultra_price: int = Field(
        default=75,
        ge=0,
        description="Ultra tier monthly price in USD"
    )
    mega_requests: int = Field(
        default=200000,
        ge=0,
        description="Mega tier requests per month"
    )
    mega_price: int = Field(
        default=150,
        ge=0,
        description="Mega tier monthly price in USD"
    )


class CacheConfig(BaseModel):
    """Cache configuration"""
    
    default_ttl: int = Field(
        default=86400,
        ge=60,
        le=2592000,
        description="Default cache TTL in seconds (24 hours)"
    )
    company_ttl: int = Field(
        default=604800,
        ge=60,
        le=2592000,
        description="Company cache TTL in seconds (7 days)"
    )
    filing_ttl: int = Field(
        default=86400,
        ge=60,
        le=2592000,
        description="Filing cache TTL in seconds (24 hours)"
    )
    max_size: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum cache entries"
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for distributed caching"
    )


class SECConfig(BaseModel):
    """SEC EDGAR API configuration"""
    
    user_agent: str = Field(
        default="YASEN-ALPHA-SEC-API/1.0 (emmayasenchak@gmail.com)",
        description="User-Agent for SEC EDGAR API (required by SEC)"
    )
    base_url: str = Field(
        default="https://www.sec.gov",
        description="SEC EDGAR base URL"
    )
    edgar_base: str = Field(
        default="https://www.sec.gov/Archives/edgar",
        description="SEC EDGAR archives base URL"
    )
    rate_limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="SEC API rate limit (requests per second)"
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="SEC API request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts"
    )


class APIConfig(BaseModel):
    """API configuration"""
    
    prefix: str = Field(
        default="/api/v1",
        description="API route prefix"
    )
    title: str = Field(
        default="YASEN-ALPHA SEC Event Intelligence API",
        description="API title"
    )
    description: str = Field(
        default="SEC Event Intelligence API providing deterministic event classification and fact extraction from SEC filings",
        description="API description"
    )
    version: str = Field(
        default="1.0.0",
        description="API version"
    )
    docs_url: str = Field(
        default="/docs",
        description="OpenAPI docs URL"
    )
    redoc_url: str = Field(
        default="/redoc",
        description="ReDoc URL"
    )
    openapi_url: str = Field(
        default="/openapi.json",
        description="OpenAPI JSON URL"
    )


class LoggingConfig(BaseModel):
    """Logging configuration"""
    
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Logging format"
    )
    json_format: bool = Field(
        default=False,
        description="Use JSON format for logs"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Log file path (optional)"
    )
    max_file_size: int = Field(
        default=10485760,  # 10MB
        ge=1024,
        description="Maximum log file size in bytes"
    )
    backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of backup log files"
    )


class DatabaseConfig(BaseModel):
    """Database configuration"""
    
    url: Optional[str] = Field(
        default=None,
        description="Database URL"
    )
    pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Connection pool size"
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Max overflow connections"
    )
    pool_timeout: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Pool timeout in seconds"
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL queries"
    )


class SecurityConfig(BaseModel):
    """Security configuration"""
    
    secret_key: SecretStr = Field(
        default=SecretStr("change-this-secret-key-in-production"),
        description="Secret key for JWT and encryption"
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    access_token_expire_minutes: int = Field(
        default=1440,  # 24 hours
        ge=1,
        le=43200,
        description="Access token expiry in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Refresh token expiry in days"
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="API key header name"
    )
    cors_origins: List[str] = Field(
        default=["*"],
        description="CORS allowed origins"
    )


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    
    enabled: bool = Field(
        default=False,
        description="Enable webhooks"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum webhook retry attempts"
    )
    retry_delay: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Webhook retry delay in seconds"
    )
    timeout: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Webhook timeout in seconds"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Webhook batch size"
    )


class MonitoringConfig(BaseModel):
    """Monitoring configuration"""
    
    enabled: bool = Field(
        default=True,
        description="Enable monitoring"
    )
    prometheus_enabled: bool = Field(
        default=False,
        description="Enable Prometheus metrics"
    )
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    new_relic_enabled: bool = Field(
        default=False,
        description="Enable New Relic monitoring"
    )
    new_relic_app_name: Optional[str] = Field(
        default=None,
        description="New Relic application name"
    )
    new_relic_license_key: Optional[str] = Field(
        default=None,
        description="New Relic license key"
    )


class OverageConfig(BaseModel):
    """Overage billing configuration"""
    
    free: float = Field(
        default=0.01,
        ge=0.0,
        description="Free tier overage price per request"
    )
    pro: float = Field(
        default=0.002,
        ge=0.0,
        description="Pro tier overage price per request"
    )
    ultra: float = Field(
        default=0.001,
        ge=0.0,
        description="Ultra tier overage price per request"
    )
    mega: float = Field(
        default=0.0005,
        ge=0.0,
        description="Mega tier overage price per request"
    )


# ============================================
# MAIN SETTINGS
# ============================================

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Settings are loaded from:
    1. Default values defined below
    2. Environment variables (prefixed with SEC_)
    3. .env file (if present)
    """
    
    # ============================================
    # BASIC SETTINGS
    # ============================================
    
    app_name: str = Field(
        default="YASEN-ALPHA SEC Event Intelligence API",
        description="Application name"
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Current environment"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Port to run the server on"
    )
    host: str = Field(
        default="0.0.0.0",
        description="Host to bind to"
    )
    workers: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of worker processes"
    )
    
    # ============================================
    # NESTED CONFIGURATIONS
    # ============================================
    
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting configuration"
    )
    pricing: PricingConfig = Field(
        default_factory=PricingConfig,
        description="Pricing configuration"
    )
    cache: CacheConfig = Field(
        default_factory=CacheConfig,
        description="Cache configuration"
    )
    sec: SECConfig = Field(
        default_factory=SECConfig,
        description="SEC EDGAR API configuration"
    )
    api: APIConfig = Field(
        default_factory=APIConfig,
        description="API configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration"
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security configuration"
    )
    webhook: WebhookConfig = Field(
        default_factory=WebhookConfig,
        description="Webhook configuration"
    )
    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig,
        description="Monitoring configuration"
    )
    overage: OverageConfig = Field(
        default_factory=OverageConfig,
        description="Overage billing configuration"
    )
    
    # ============================================
    # VALIDATORS
    # ============================================
    
    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: Union[str, Environment]) -> Environment:
        """Validate environment value"""
        if isinstance(v, Environment):
            return v
        if isinstance(v, str):
            v_lower = v.lower()
            for env in Environment:
                if env.value == v_lower:
                    return env
            raise ValueError(f"Invalid environment: {v}")
        raise ValueError(f"Invalid environment type: {type(v)}")
    
    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, v: Union[bool, str]) -> bool:
        """Validate debug value"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return False
    
    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        """Validate security settings"""
        if self.environment == Environment.PRODUCTION:
            # In production, secret key must be changed from default
            if self.security.secret_key.get_secret_value() == "change-this-secret-key-in-production":
                raise ValueError(
                    "SECURITY_SECRET_KEY must be changed from default in production"
                )
        return self
    
    @model_validator(mode="after")
    def validate_cors(self) -> "Settings":
        """Validate CORS settings"""
        if self.environment == Environment.PRODUCTION:
            if "*" in self.security.cors_origins and len(self.security.cors_origins) > 1:
                # If "*" is present with other origins, it's redundant
                self.security.cors_origins = ["*"]
        return self
    
    # ============================================
    # CONVENIENCE PROPERTIES
    # ============================================
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode"""
        return self.environment == Environment.STAGING
    
    @property
    def is_test(self) -> bool:
        """Check if running in test mode"""
        return self.environment == Environment.TEST
    
    @property
    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.debug or self.is_development
    
    # ============================================
    # HELPER METHODS
    # ============================================
    
    def get_rate_limit_for_tier(self, tier: str) -> int:
        """
        Get rate limit for a specific tier.
        
        Args:
            tier: Tier name (free, pro, ultra, mega)
            
        Returns:
            Rate limit in requests per minute
        """
        tier_map = {
            "free": self.rate_limit.free,
            "pro": self.rate_limit.pro,
            "ultra": self.rate_limit.ultra,
            "mega": self.rate_limit.mega,
        }
        return tier_map.get(tier.lower(), self.rate_limit.free)
    
    def get_pricing_for_tier(self, tier: str) -> Dict[str, Any]:
        """
        Get pricing for a specific tier.
        
        Args:
            tier: Tier name (free, pro, ultra, mega)
            
        Returns:
            Pricing dictionary
        """
        tier_map = {
            "free": {
                "price": 0,
                "requests_per_month": self.pricing.free_requests,
                "rate_limit": self.rate_limit.free,
            },
            "pro": {
                "price": self.pricing.pro_price,
                "requests_per_month": self.pricing.pro_requests,
                "rate_limit": self.rate_limit.pro,
            },
            "ultra": {
                "price": self.pricing.ultra_price,
                "requests_per_month": self.pricing.ultra_requests,
                "rate_limit": self.rate_limit.ultra,
            },
            "mega": {
                "price": self.pricing.mega_price,
                "requests_per_month": self.pricing.mega_requests,
                "rate_limit": self.rate_limit.mega,
            },
        }
        return tier_map.get(tier.lower(), tier_map["free"])
    
    def get_overage_price_for_tier(self, tier: str) -> float:
        """
        Get overage price for a specific tier.
        
        Args:
            tier: Tier name (free, pro, ultra, mega)
            
        Returns:
            Overage price per request
        """
        tier_map = {
            "free": self.overage.free,
            "pro": self.overage.pro,
            "ultra": self.overage.ultra,
            "mega": self.overage.mega,
        }
        return tier_map.get(tier.lower(), self.overage.free)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert settings to dictionary (excluding secrets).
        
        Returns:
            Dictionary of settings
        """
        result = {}
        
        for key, value in self.__dict__.items():
            # Skip private attributes
            if key.startswith("_"):
                continue
            
            # Handle SecretStr
            if isinstance(value, SecretStr):
                result[key] = "***REDACTED***"
            # Handle nested models
            elif hasattr(value, "model_dump"):
                result[key] = value.model_dump()
            # Handle other types
            else:
                result[key] = value
        
        return result
    
    class Config:
        """Pydantic configuration"""
        
        env_file = str(ENV_FILE) if ENV_FILE.exists() else None
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables
        
        # Environment variable prefix
        env_prefix = "SEC_"
        
        # Use nested environment variables
        # Example: SEC_RATE_LIMIT__FREE=10
        env_nested_delimiter = "__"
        
        json_schema_extra = {
            "example": {
                "app_name": "YASEN-ALPHA SEC Event Intelligence API",
                "app_version": "1.0.0",
                "environment": "development",
                "debug": True,
                "port": 8000,
                "rate_limit": {
                    "free": 10,
                    "pro": 20,
                    "ultra": 40,
                    "mega": 60,
                },
                "pricing": {
                    "free_requests": 500,
                    "pro_requests": 10000,
                    "pro_price": 19,
                    "ultra_requests": 50000,
                    "ultra_price": 49,
                    "mega_requests": 200000,
                    "mega_price": 149,
                },
                "cache": {
                    "default_ttl": 86400,
                    "max_size": 10000,
                },
                "sec": {
                    "user_agent": "YASEN-ALPHA-SEC-API/1.0 (email@example.com)",
                    "rate_limit": 10,
                },
            }
        }


# ============================================
# SINGLETON INSTANCE
# ============================================

_settings: Optional[Settings] = None


@lru_cache()
def get_settings() -> Settings:
    """
    Get the singleton settings instance.
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
            logger = logging.getLogger(__name__)
            logger.info(f"Settings loaded: {_settings.environment} mode")
            logger.info(f"App: {_settings.app_name} v{_settings.app_version}")
        except Exception as e:
            print(f"ERROR loading settings: {e}")
            raise
    return _settings


# ============================================
# COMPATIBILITY ALIASES
# ============================================

# Provide backwards compatibility with existing code
settings = get_settings()

# Export commonly used settings as module-level variables
APP_NAME = settings.app_name
APP_VERSION = settings.app_version
ENVIRONMENT = settings.environment
DEBUG = settings.debug
PORT = settings.port
HOST = settings.host

# Rate limits
RATE_LIMIT_FREE = settings.rate_limit.free
RATE_LIMIT_PRO = settings.rate_limit.pro
RATE_LIMIT_ULTRA = settings.rate_limit.ultra
RATE_LIMIT_MEGA = settings.rate_limit.mega
RATE_LIMIT_WINDOW = settings.rate_limit.window

# Pricing
PRICING_FREE_REQUESTS = settings.pricing.free_requests
PRICING_PRO_REQUESTS = settings.pricing.pro_requests
PRICING_PRO_PRICE = settings.pricing.pro_price
PRICING_ULTRA_REQUESTS = settings.pricing.ultra_requests
PRICING_ULTRA_PRICE = settings.pricing.ultra_price
PRICING_MEGA_REQUESTS = settings.pricing.mega_requests
PRICING_MEGA_PRICE = settings.pricing.mega_price

# Cache
CACHE_TTL = settings.cache.default_ttl
CACHE_MAX_SIZE = settings.cache.max_size

# SEC
SEC_USER_AGENT = settings.sec.user_agent
SEC_BASE_URL = settings.sec.base_url
SEC_EDGAR_BASE = settings.sec.edgar_base
SEC_RATE_LIMIT = settings.sec.rate_limit
SEC_TIMEOUT = settings.sec.timeout

# API
API_PREFIX = settings.api.prefix
API_TITLE = settings.api.title
API_DESCRIPTION = settings.api.description
API_VERSION = settings.api.version

# Logging
LOG_LEVEL = settings.logging.level.value

# Overage
OVERAGE_FREE = settings.overage.free
OVERAGE_PRO = settings.overage.pro
OVERAGE_ULTRA = settings.overage.ultra
OVERAGE_MEGA = settings.overage.mega


# ============================================
# EXPORTS
# ============================================

__all__ = [
    # Main settings
    "Settings",
    "settings",
    "get_settings",
    
    # Enums
    "Environment",
    "LogLevel",
    
    # Config models
    "RateLimitConfig",
    "PricingConfig",
    "CacheConfig",
    "SECConfig",
    "APIConfig",
    "LoggingConfig",
    "DatabaseConfig",
    "SecurityConfig",
    "WebhookConfig",
    "MonitoringConfig",
    "OverageConfig",
    
    # Module-level constants
    "APP_NAME",
    "APP_VERSION",
    "ENVIRONMENT",
    "DEBUG",
    "PORT",
    "HOST",
    "RATE_LIMIT_FREE",
    "RATE_LIMIT_PRO",
    "RATE_LIMIT_ULTRA",
    "RATE_LIMIT_MEGA",
    "RATE_LIMIT_WINDOW",
    "PRICING_FREE_REQUESTS",
    "PRICING_PRO_REQUESTS",
    "PRICING_PRO_PRICE",
    "PRICING_ULTRA_REQUESTS",
    "PRICING_ULTRA_PRICE",
    "PRICING_MEGA_REQUESTS",
    "PRICING_MEGA_PRICE",
    "CACHE_TTL",
    "CACHE_MAX_SIZE",
    "SEC_USER_AGENT",
    "SEC_BASE_URL",
    "SEC_EDGAR_BASE",
    "SEC_RATE_LIMIT",
    "SEC_TIMEOUT",
    "API_PREFIX",
    "API_TITLE",
    "API_DESCRIPTION",
    "API_VERSION",
    "LOG_LEVEL",
    "OVERAGE_FREE",
    "OVERAGE_PRO",
    "OVERAGE_ULTRA",
    "OVERAGE_MEGA",
]