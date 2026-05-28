"""
API Monitoring and Health Check System
Tracks API performance, errors, and availability
"""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List
import aiohttp
from platform.src.pipeline.external_api.api_client import AwardTravelAPIIntegrator
from platform.src.pipeline.external_api.exceptions import APIError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class APIMonitor:
    """Monitors the health and performance of external APIs"""

    def __init__(self, integrator: AwardTravelAPIIntegrator):
        self.integrator = integrator
        self.health_data: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, List[float]] = {
            "flight": [],
            "hotel": [],
            "car": []
        }
        self.error_counts: Dict[str, int] = {
            "flight": 0,
            "hotel": 0,
            "car": 0
        }

    async def check_api_health(self) -> Dict[str, Any]:
        """Perform health checks on all APIs"""
        health_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
            "overall_status": "healthy"
        }

        # Check flight API
        flight_status = await self._check_service("flight")
        health_report["services"]["flight"] = flight_status

        # Check hotel API
        hotel_status = await self._check_service("hotel")
        health_report["services"]["hotel"] = hotel_status

        # Check car API
        car_status = await self._check_service("car")
        health_report["services"]["car"] = car_status

        # Determine overall status
        all_healthy = all(
            status["status"] == "healthy"
            for status in health_report["services"].values()
        )
        health_report["overall_status"] = "healthy" if all_healthy else "degraded"

        return health_report

    async def _check_service(self, service: str) -> Dict[str, Any]:
        """Check health of a specific service"""
        start_time = datetime.utcnow()
        status = {
            "status": "unhealthy",
            "response_time_ms": 0,
            "error": None
        }

        try:
            if service == "flight":
                async with self.integrator.flight_client:
                    # Perform a lightweight check
                    await self.integrator.flight_client.search_flights(
                        origin="JFK",
                        destination="LAX",
                        departure_date=(datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
                        limit=1
                    )
            elif service == "hotel":
                async with self.integrator.hotel_client:
                    await self.integrator.hotel_client.search_hotels(
                        location="New York",
                        check_in=(datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
                        check_out=(datetime.utcnow() + timedelta(days=8)).strftime("%Y-%m-%d"),
                        limit=1
                    )
            elif service == "car":
                async with self.integrator.car_client:
                    await self.integrator.car_client.search_vehicles(
                        location="New York",
                        from_time=(datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT09:00:00"),
                        to_time=(datetime.utcnow() + timedelta(days=8)).strftime("%Y-%m-%dT17:00:00"),
                        limit=1
                    )

            status["status"] = "healthy"
            status["response_time_ms"] = (datetime.utcnow() - start_time).total_seconds() * 1000

        except APIError as e:
            status["status"] = "error"
            status["error"] = str(e)
            self.error_counts[service] += 1
        except Exception as e:
            status["status"] = "unhealthy"
            status["error"] = f"Unexpected error: {str(e)}"
            self.error_counts[service] += 1

        return status

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get aggregated performance metrics"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                service: {
                    "avg_response_time_ms": sum(times) / len(times) if times else 0,
                    "request_count": len(times),
                    "error_count": self.error_counts.get(service, 0)
                }
                for service, times in self.performance_metrics.items()
            }
        }

    async def start_monitoring_loop(self, interval: int = 60):
        """Start a background monitoring loop"""
        logger.info("Starting API monitoring loop")
        while True:
            try:
                # Check health
                health = await self.check_api_health()
                logger.info(f"API Health Report: {health['overall_status']}")

                # Record metrics
                for service, status in health["services"].items():
                    if status["status"] == "healthy":
                        self.performance_metrics[service].append(status["response_time_ms"])

                # Keep metrics window to last 1000 requests
                for service in self.performance_metrics:
                    if len(self.performance_metrics[service]) > 1000:
                        self.performance_metrics[service] = self.performance_metrics[service][-1000:]

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Monitoring loop error: {str(e)}")
                await asyncio.sleep(interval)
