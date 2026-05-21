#!/usr/bin/env python3
"""
Chaos Monkey - Automated Failure Injection Platform
District Award Travel - Resilience Engineering
"""

import os
import sys
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import uvicorn
import yaml
import aioredis
import motor.motor_asyncio
import requests
from croniter import croniter

# Initialize FastAPI app
app = FastAPI(title="Chaos Monkey API", version="1.0.0")

# Configuration
CONFIG_PATH = os.getenv("CHAOS_CONFIG_PATH", "/app/config/chaos-config.yml")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/chaos")
REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379/0")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Metrics
CHAOS_EVENTS_COUNTER = Counter(
    'chaos_events_total',
    'Total number of chaos events executed',
    ['event_type', 'target', 'severity']
)
CHAOS_LATENCY_HISTOGRAM = Histogram(
    'chaos_event_latency_seconds',
    'Latency of chaos events',
    ['event_type']
)
SYSTEM_HEALTH_GAUGE = Gauge(
    'system_health_score',
    'Overall system health score (0-100)'
)
FAILURE_RATE_GAUGE = Gauge(
    'failure_rate_percentage',
    'Current failure rate percentage'
)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            '/app/logs/chaos-monkey.log',
            maxBytes=10485760,
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChaosMonkey:
    """Core Chaos Monkey Engine"""

    def __init__(self):
        self.config = self._load_config()
        self.redis = None
        self.mongo = None
        self._initialize_clients()
        self._validate_config()
        logger.info("Chaos Monkey initialized successfully")

    def _load_config(self) -> Dict[str, Any]:
        """Load chaos configuration from YAML file"""
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {CONFIG_PATH}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def _initialize_clients(self):
        """Initialize database clients"""
        try:
            # MongoDB client
            self.mongo = motor.motor_asyncio.AsyncIOMotorClient(
                MONGO_URI,
                username=os.getenv("MONGO_USER", "chaos"),
                password=os.getenv("MONGO_PASSWORD", "chaos123")
            )

            # Redis client
            self.redis = aioredis.from_url(
                REDIS_URI,
                password=os.getenv("REDIS_PASSWORD", "chaos123")
            )

            logger.info("Database clients initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database clients: {e}")
            raise

    def _validate_config(self):
        """Validate chaos configuration"""
        required_sections = ['targets', 'scenarios', 'schedules']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")

        logger.info("Configuration validation passed")

    async def _record_event(self, event_type: str, target: str, severity: str, status: str, details: Dict[str, Any]):
        """Record chaos event in database"""
        try:
            event = {
                "event_type": event_type,
                "target": target,
                "severity": severity,
                "status": status,
                "timestamp": datetime.utcnow(),
                "details": details
            }

            db = self.mongo.chaos.events
            await db.insert_one(event)

            # Update metrics
            CHAOS_EVENTS_COUNTER.labels(
                event_type=event_type,
                target=target,
                severity=severity
            ).inc()

            logger.info(f"Recorded chaos event: {event_type} on {target}")
        except Exception as e:
            logger.error(f"Failed to record event: {e}")

    async def _execute_scenario(self, scenario: Dict[str, Any]):
        """Execute a single chaos scenario"""
        event_type = scenario.get('type', 'unknown')
        target = scenario.get('target', 'unknown')
        severity = scenario.get('severity', 'medium')
        duration = scenario.get('duration', 30)

        logger.info(f"Executing {event_type} on {target} (severity: {severity})")

        start_time = datetime.utcnow()

        try:
            # Execute scenario
            if event_type == 'kill_container':
                await self._kill_container(target)
            elif event_type == 'network_latency':
                await self._inject_network_latency(target, duration)
            elif event_type == 'cpu_stress':
                await self._stress_cpu(target, duration)
            elif event_type == 'memory_leak':
                await self._inject_memory_leak(target, duration)
            elif event_type == 'disk_fill':
                await self._fill_disk(target, duration)
            elif event_type == 'api_failure':
                await self._simulate_api_failure(target)
            else:
                logger.warning(f"Unknown scenario type: {event_type}")
                return

            # Record successful event
            await self._record_event(
                event_type=event_type,
                target=target,
                severity=severity,
                status="success",
                details={
                    "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                    "timestamp": start_time.isoformat()
                }
            )

        except Exception as e:
            logger.error(f"Failed to execute scenario {event_type} on {target}: {e}")

            # Record failed event
            await self._record_event(
                event_type=event_type,
                target=target,
                severity=severity,
                status="failed",
                details={
                    "error": str(e),
                    "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                    "timestamp": start_time.isoformat()
                }
            )

    async def _kill_container(self, container_name: str):
        """Kill a Docker container"""
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_name)
            container.kill()
            logger.info(f"Killed container: {container_name}")
        except Exception as e:
            logger.error(f"Failed to kill container {container_name}: {e}")
            raise

    async def _inject_network_latency(self, target: str, duration: int):
        """Inject network latency using tc (traffic control)"""
        try:
            # This would be implemented with actual network manipulation
            # For now, simulate the effect
            logger.info(f"Injecting {duration}s network latency on {target}")
            await asyncio.sleep(duration)
        except Exception as e:
            logger.error(f"Failed to inject network latency: {e}")
            raise

    async def _stress_cpu(self, target: str, duration: int):
        """Stress CPU on target"""
        try:
            # This would be implemented with actual CPU stress tools
            logger.info(f"Stressing CPU on {target} for {duration}s")
            await asyncio.sleep(duration)
        except Exception as e:
            logger.error(f"Failed to stress CPU: {e}")
            raise

    async def _inject_memory_leak(self, target: str, duration: int):
        """Inject memory leak on target"""
        try:
            logger.info(f"Injecting memory leak on {target} for {duration}s")
            await asyncio.sleep(duration)
        except Exception as e:
            logger.error(f"Failed to inject memory leak: {e}")
            raise

    async def _fill_disk(self, target: str, duration: int):
        """Fill disk space on target"""
        try:
            logger.info(f"Filling disk on {target} for {duration}s")
            await asyncio.sleep(duration)
        except Exception as e:
            logger.error(f"Failed to fill disk: {e}")
            raise

    async def _simulate_api_failure(self, target: str):
        """Simulate API failures by returning 5xx errors"""
        try:
            # This would be implemented with actual API proxy manipulation
            logger.info(f"Simulating API failure on {target}")
        except Exception as e:
            logger.error(f"Failed to simulate API failure: {e}")
            raise

    async def run_scenarios(self):
        """Run all scheduled chaos scenarios"""
        logger.info("Starting chaos scenario execution")

        while True:
            try:
                # Get current time
                now = datetime.utcnow()

                # Check each scenario
                for scenario in self.config.get('scenarios', []):
                    schedule = scenario.get('schedule')
                    if schedule and self._should_run_now(schedule, now):
                        await self._execute_scenario(scenario)

                # Sleep for a short interval
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in scenario execution loop: {e}")
                await asyncio.sleep(60)

    def _should_run_now(self, schedule: str, now: datetime) -> bool:
        """Check if scenario should run now based on cron schedule"""
        try:
            cron = croniter(schedule, now)
            next_run = cron.get_next(datetime)
            return next_run <= now
        except Exception as e:
            logger.error(f"Invalid cron schedule {schedule}: {e}")
            return False

    async def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            # This would integrate with actual health checks
            health_score = 95  # Default for demo
            failure_rate = 2.5  # Default for demo

            SYSTEM_HEALTH_GAUGE.set(health_score)
            FAILURE_RATE_GAUGE.set(failure_rate)

            return {
                "status": "healthy" if health_score > 80 else "degraded",
                "health_score": health_score,
                "failure_rate": failure_rate,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# Initialize Chaos Monkey
chaos_monkey = ChaosMonkey()

# FastAPI Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "chaos-monkey"}

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.get("/events")
async def get_events(limit: int = 100):
    """Get recent chaos events"""
    try:
        db = chaos_monkey.mongo.chaos.events
        events = await db.find().sort("timestamp", -1).limit(limit).to_list(None)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scenarios")
async def get_scenarios():
    """Get all configured chaos scenarios"""
    return {"scenarios": chaos_monkey.config.get('scenarios', [])}

@app.post("/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """Manually trigger a chaos scenario"""
    try:
        scenario = next(
            (s for s in chaos_monkey.config.get('scenarios', [])
             if s.get('id') == scenario_id),
            None
        )

        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        await chaos_monkey._execute_scenario(scenario)
        return {"status": "triggered", "scenario": scenario_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get system status"""
    return await chaos_monkey.get_health_status()

def main():
    """Main entry point"""
    logger.info("Starting Chaos Monkey service")

    # Start metrics server
    start_http_server(METRICS_PORT)
    logger.info(f"Metrics server started on port {METRICS_PORT}")

    # Start scenario execution
    asyncio.create_task(chaos_monkey.run_scenarios())

    # Start FastAPI server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9090,
        log_config=None,
        log_level="info"
    )

if __name__ == "__main__":
    main()
