import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
from functools import wraps
import json
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class AirlineRequest:
    airline_code: str
    endpoint: str
    params: Dict[str, Any]
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None

@dataclass
class AirlineResponse:
    status_code: int
    data: Dict[str, Any]
    headers: Dict[str, str]
    cached: bool
    timestamp: datetime
    request_id: str

class CircuitBreaker:
    def __init__(self, max_failures: int = 5, reset_timeout: int = 60):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"
        self.lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        async with self.lock:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.reset_timeout:
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            async with self.lock:
                if self.state == "half-open":
                    self.state = "closed"
                    self.failures = 0
            return result
        except Exception as e:
            async with self.lock:
                self.failures += 1
                self.last_failure_time = time.time()
                if self.failures >= self.max_failures:
                    self.state = "open"
            logger.error(f"Circuit breaker tripped for {func.__name__}: {str(e)}")
            raise

class CacheManager:
    def __init__(self, cache_dir: str = "/tmp/airline_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)

    def _get_cache_key(self, request: AirlineRequest) -> str:
        key_str = f"{request.airline_code}:{request.endpoint}:{json.dumps(request.params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, request: AirlineRequest) -> Optional[AirlineResponse]:
        cache_key = self._get_cache_key(request)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                return AirlineResponse(
                    status_code=data['status_code'],
                    data=data['data'],
                    headers=data['headers'],
                    cached=True,
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    request_id=data['request_id']
                )
            except Exception as e:
                logger.warning(f"Cache read failed: {str(e)}")
                return None
        return None

    def set(self, request: AirlineRequest, response: AirlineResponse, ttl: int = 300):
        cache_key = self._get_cache_key(request)
        cache_file = self.cache_dir / f"{cache_key}.json"

        data = {
            'status_code': response.status_code,
            'data': response.data,
            'headers': response.headers,
            'timestamp': response.timestamp.isoformat(),
            'request_id': response.request_id
        }

        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            # Set file modification time for TTL
            cache_file.touch(exist_time=ttl)
        except Exception as e:
            logger.error(f"Cache write failed: {str(e)}")

class BaseAirlineClient(ABC):
    def __init__(self, api_key: str, base_url: str, circuit_breaker: CircuitBreaker, cache_manager: CacheManager):
        self.api_key = api_key
        self.base_url = base_url
        self.circuit_breaker = circuit_breaker
        self.cache_manager = cache_manager
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": "DistrictAwardTravel/1.0"}
        )

    async def close(self):
        await self.client.aclose()

    async def _make_request(self, request: AirlineRequest) -> AirlineResponse:
        # Check cache first
        cached_response = self.cache_manager.get(request)
        if cached_response:
            logger.info(f"Cache hit for {request.airline_code}:{request.endpoint}")
            return cached_response

        # Use circuit breaker for the actual request
        try:
            response = await self.circuit_breaker.call(self._execute_request, request)
            # Cache successful responses
            if response.status_code == 200:
                self.cache_manager.set(request, response)
            return response
        except RetryError as e:
            logger.error(f"Request failed after retries: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    @abstractmethod
    async def _execute_request(self, request: AirlineRequest) -> AirlineResponse:
        pass

    @abstractmethod
    def validate_response(self, response: AirlineResponse) -> bool:
        pass

class UnitedClient(BaseAirlineClient):
    def __init__(self, api_key: str, circuit_breaker: CircuitBreaker, cache_manager: CacheManager):
        super().__init__(
            api_key=api_key,
            base_url="https://api.united.com/v1",
            circuit_breaker=circuit_breaker,
            cache_manager=cache_manager
        )

    async def _execute_request(self, request: AirlineRequest) -> AirlineResponse:
        url = f"{self.base_url}/{request.endpoint}"
        headers = request.headers or {}
        headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

        start_time = time.time()

        try:
            if request.method == "GET":
                resp = await self.client.get(
                    url,
                    params=request.params,
                    headers=headers
                )
            elif request.method == "POST":
                resp = await self.client.post(
                    url,
                    json=request.body,
                    headers=headers
                )
            else:
                raise ValueError(f"Unsupported method: {request.method}")

            response_time = time.time() - start_time

            try:
                data = resp.json()
            except ValueError:
                data = {"raw_response": resp.text}

            logger.info(
                f"United API request completed in {response_time:.3f}s - "
                f"Status: {resp.status_code}, URL: {url}"
            )

            return AirlineResponse(
                status_code=resp.status_code,
                data=data,
                headers=dict(resp.headers),
                cached=False,
                timestamp=datetime.utcnow(),
                request_id=resp.headers.get('x-request-id', '')
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"United API error: {str(e)} - Status: {e.response.status_code}")
            return AirlineResponse(
                status_code=e.response.status_code,
                data={"error": str(e)},
                headers=dict(e.response.headers),
                cached=False,
                timestamp=datetime.utcnow(),
                request_id=e.response.headers.get('x-request-id', '')
            )
        except httpx.RequestError as e:
            logger.error(f"United API request failed: {str(e)}")
            raise

    def validate_response(self, response: AirlineResponse) -> bool:
        if response.status_code != 200:
            return False

        # Basic validation for United API responses
        if not isinstance(response.data, dict):
            return False

        # Check for error in response
        if "error" in response.data:
            return False

        return True

class DeltaClient(BaseAirlineClient):
    def __init__(self, api_key: str, circuit_breaker: CircuitBreaker, cache_manager: CacheManager):
        super().__init__(
            api_key=api_key,
            base_url="https://api.delta.com/sky-miles/v1",
            circuit_breaker=circuit_breaker,
            cache_manager=cache_manager
        )

    async def _execute_request(self, request: AirlineRequest) -> AirlineResponse:
        url = f"{self.base_url}/{request.endpoint}"
        headers = request.headers or {}
        headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        })

        start_time = time.time()

        try:
            if request.method == "GET":
                resp = await self.client.get(
                    url,
                    params=request.params,
                    headers=headers
                )
            elif request.method == "POST":
                resp = await self.client.post(
                    url,
                    json=request.body,
                    headers=headers
                )
            else:
                raise ValueError(f"Unsupported method: {request.method}")

            response_time = time.time() - start_time

            try:
                data = resp.json()
            except ValueError:
                data = {"raw_response": resp.text}

            logger.info(
                f"Delta API request completed in {response_time:.3f}s - "
                f"Status: {resp.status_code}, URL: {url}"
            )

            return AirlineResponse(
                status_code=resp.status_code,
                data=data,
                headers=dict(resp.headers),
                cached=False,
                timestamp=datetime.utcnow(),
                request_id=resp.headers.get('x-request-id', '')
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Delta API error: {str(e)} - Status: {e.response.status_code}")
            return AirlineResponse(
                status_code=e.response.status_code,
                data={"error": str(e)},
                headers=dict(e.response.headers),
                cached=False,
                timestamp=datetime.utcnow(),
                request_id=e.response.headers.get('x-request-id', '')
            )
        except httpx.RequestError as e:
            logger.error(f"Delta API request failed: {str(e)}")
            raise

    def validate_response(self, response: AirlineResponse) -> bool:
        if response.status_code != 200:
            return False

        if not isinstance(response.data, dict):
            return False

        if "error" in response.data:
            return False

        return True

class AmericanClient(BaseAirlineClient):
    def __init__(self, api_key: str, circuit_breaker: CircuitBreaker, cache_manager: CacheManager):
        super().__init__(
            api_key=api_key,
            base_url="https://api.americanairlines.com/v1",
            circuit_breaker=circuit_breaker,
            cache_manager=cache_manager
        )

    async def _execute_request(self, request: AirlineRequest) -> AirlineResponse:
        url = f"{self.base_url}/{request.endpoint}"
        headers = request.headers or {}
        headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-app-id": "district-award-travel"
        })

        start_time = time.time()

        try:
            if request.method == "GET":
                resp = await self.client.get(
                    url,
                    params=request.params,
                    headers=headers
                )
            elif request.method == "POST":
                resp = await self.client.post(
                    url,
                    json=request.body,
                    headers=headers
                )
            else:
                raise ValueError(f"Unsupported method: {request.method}")

            response_time = time.time() - start_time

            try:
                data = resp.json()
            except ValueError:
                data = {"raw_response": resp.text}

            logger.info(
                f"American API request completed in {response_time:.3f}s - "
                f"Status: {resp.status_code}, URL: {url}"
            )

            return AirlineResponse(
                status_code=resp.status_code,
                data=data,
                headers=dict(resp.headers),
                cached=False,
                timestamp=datetime.utcnow(),
                request_id=resp.headers.get('x-request-id', '')
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"American API error: {str(e)} - Status: {e.response.status_code}")
            return AirlineResponse(
                status_code=e.response.status_code,
                data={"error": str(e)},
                headers=dict(e.response.headers),
                cached=False,
                timestamp=datetime.utcnow(),
                request_id=e.response.headers.get('x-request-id', '')
            )
        except httpx.RequestError as e:
            logger.error(f"American API request failed: {str(e)}")
            raise

    def validate_response(self, response: AirlineResponse) -> bool:
        if response.status_code != 200:
            return False

        if not isinstance(response.data, dict):
            return False

        if "error" in response.data:
            return False

        return True

class AirlineClientFactory:
    @staticmethod
    def create_client(
        airline: str,
        api_key: str,
        circuit_breaker: CircuitBreaker,
        cache_manager: CacheManager
    ) -> BaseAirlineClient:
        airline = airline.lower()
        if airline == "united":
            return UnitedClient(api_key, circuit_breaker, cache_manager)
        elif airline == "delta":
            return DeltaClient(api_key, circuit_breaker, cache_manager)
        elif airline == "american":
            return AmericanClient(api_key, circuit_breaker, cache_manager)
        else:
            raise ValueError(f"Unsupported airline: {airline}")

# Decorator for retry logic
def with_retry(max_attempts: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed. Retrying in {delay:.2f}s. Error: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    continue

            raise last_exception
        return wrapper
    return decorator
