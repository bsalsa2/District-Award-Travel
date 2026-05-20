#!/usr/bin/env python3
"""
Alerting service with comprehensive logging and health monitoring
for District Award Travel's award travel systems.
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Any

import structlog
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pythonjsonlogger import jsonlogger

# Initialize FastAPI app
app = FastAPI(
    title="District Award Travel Alerting System",
    description="Comprehensive alerting and monitoring for award travel operations",
    version="1.0.0"
)

# Configure structured logging
def configure_logging():
    """Configure structured logging with multiple handlers."""
    logger = structlog.get_logger()

    # JSON formatter for file logging
    json_formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(lineno)d %(pathname)s'
    )

    # Console formatter for development
    console_formatter = structlog.dev.ConsoleRenderer()

    # File handler for persistent logs
    file_handler = logging.FileHandler('/var/log/alerting/alerting-service.log')
    file_handler.setFormatter(json_formatter)

    # Console handler for stdout
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )

    # Bind structured logging context
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )

    return logger

# Initialize logging
logger = configure_logging()

# Metrics definitions
ALERTS_TRIGGERED = Counter(
    'alerts_triggered_total',
    'Total number of alerts triggered',
    ['alert_type', 'severity']
)

ALERT_RESPONSE_TIME = Histogram(
    'alert_response_time_seconds',
    'Time taken to process and respond to alerts',
    ['alert_type']
)

SYSTEM_HEALTH = Gauge(
    'system_health_status',
    'Overall health status of the alerting system (1=healthy, 0=unhealthy)'
)

LAST_HEARTBEAT = Gauge(
    'last_heartbeat_timestamp',
    'Timestamp of last successful heartbeat'
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring system health."""
    try:
        # Check if system is responsive
        current_time = time.time()
        LAST_HEARTBEAT.set(current_time)

        # Simulate health check logic
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "system": "operational",
                "database": "connected",
                "external_services": "available"
            }
        }

        logger.info("Health check passed", **health_status)
        SYSTEM_HEALTH.set(1)

        return JSONResponse(
            content=health_status,
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        SYSTEM_HEALTH.set(0)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System unhealthy"
        )

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

# Alert endpoint
@app.post("/alert")
async def trigger_alert(alert_data: Dict[str, Any]):
    """Endpoint to trigger alerts with structured logging."""
    try:
        with ALERT_RESPONSE_TIME.labels(alert_type=alert_data.get('type', 'unknown')).time():
            # Validate alert data
            if not alert_data.get('type'):
                raise ValueError("Alert type is required")

            if not alert_data.get('message'):
                raise ValueError("Alert message is required")

            # Log the alert with structured data
            log_data = {
                "alert_id": alert_data.get('id', f"alert-{int(time.time())}"),
                "alert_type": alert_data['type'],
                "severity": alert_data.get('severity', 'medium'),
                "message": alert_data['message'],
                "timestamp": datetime.utcnow().isoformat(),
                "context": alert_data.get('context', {}),
                "source": alert_data.get('source', 'api')
            }

            # Log at appropriate level based on severity
            severity = log_data['severity'].lower()
            if severity == 'critical':
                logger.critical("Critical alert triggered", **log_data)
            elif severity == 'high':
                logger.error("High severity alert triggered", **log_data)
            elif severity == 'medium':
                logger.warning("Medium severity alert triggered", **log_data)
            else:
                logger.info("Alert triggered", **log_data)

            # Increment alert counter
            ALERTS_TRIGGERED.labels(
                alert_type=log_data['alert_type'],
                severity=log_data['severity']
            ).inc()

            return JSONResponse(
                content={
                    "status": "alert triggered",
                    "alert_id": log_data['alert_id'],
                    "timestamp": log_data['timestamp']
                },
                status_code=status.HTTP_201_CREATED
            )
    except Exception as e:
        logger.error("Failed to process alert", error=str(e), alert_data=alert_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Log aggregation endpoint
@app.post("/log")
async def receive_log(log_entry: Dict[str, Any]):
    """Endpoint to receive log entries from other services."""
    try:
        # Validate log entry
        if not log_entry.get('message'):
            raise ValueError("Log message is required")

        # Add timestamp if not present
        if not log_entry.get('timestamp'):
            log_entry['timestamp'] = datetime.utcnow().isoformat()

        # Log the entry with appropriate level
        level = log_entry.get('level', 'info').lower()
        if level == 'critical':
            logger.critical("Received log entry", **log_entry)
        elif level == 'error':
            logger.error("Received log entry", **log_entry)
        elif level == 'warning':
            logger.warning("Received log entry", **log_entry)
        elif level == 'debug':
            logger.debug("Received log entry", **log_entry)
        else:
            logger.info("Received log entry", **log_entry)

        return JSONResponse(
            content={"status": "log received"},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error("Failed to process log entry", error=str(e), log_entry=log_entry)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_config=None  # Using our structured logging instead
    )
