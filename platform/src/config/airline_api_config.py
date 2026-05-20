import os
from typing import Dict, Any

def get_airline_api_config() -> Dict[str, Any]:
    """
    Get configuration for airline API integration
    """
    return {
        "airlines": ["united", "delta", "american"],
        "api_keys": {
            "united": os.getenv("UNITED_API_KEY", "test_united_key"),
            "delta": os.getenv("DELTA_API_KEY", "test_delta_key"),
            "american": os.getenv("AMERICAN_API_KEY", "test_american_key")
        },
        "circuit_breaker_max_failures": int(os.getenv("CIRCUIT_BREAKER_MAX_FAILURES", "5")),
        "circuit_breaker_reset_timeout": int(os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT", "60")),
        "cache_dir": os.getenv("AIRLINE_CACHE_DIR", "/tmp/airline_cache"),
        "request_timeout": float(os.getenv("AIRLINE_REQUEST_TIMEOUT", "10.0")),
        "max_concurrent_requests": int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
        "retry_attempts": int(os.getenv("RETRY_ATTEMPTS", "3")),
        "retry_base_delay": float(os.getenv("RETRY_BASE_DELAY", "1.0"))
    }
