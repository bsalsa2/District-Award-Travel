"""
Custom exceptions for external API integrations
"""

class APIError(Exception):
    """Base class for API-related errors"""
    pass

class APIRateLimitExceeded(APIError):
    """Raised when API rate limit is exceeded"""
    pass

class APITimeoutError(APIError):
    """Raised when API request times out"""
    pass

class APIAuthError(APIError):
    """Raised when API authentication fails"""
    pass

class APIDataError(APIError):
    """Raised when API returns invalid data"""
    pass

class CacheError(Exception):
    """Raised when cache operation fails"""
    pass
