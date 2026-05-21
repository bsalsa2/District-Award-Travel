# -*- coding: utf-8 -*-
# FILE: platform/infra/scripts/health/monitor.py

import os
import time
import logging
import requests
import schedule
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger
import psutil

# Configure logging
log_handler = logging.StreamHandler()
log_formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
log_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Configuration
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
CHECK_INTERVAL = 60  # seconds
LOG_FILE = "/var/log/health/monitor.log"

def log_to_file(message: dict):
    """Log health check results to file"""
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(message) + '\n')
    except Exception as e:
        logger.error(f"Failed to write to log file: {str(e)}")

def check_service_health(service_name: str, url: str, expected_status: int = 200) -> dict:
    """Check if a service is healthy"""
    try:
        response = requests.get(url, timeout=5)
        is_healthy = response.status_code == expected_status

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": service_name,
            "url": url,
            "status": "healthy" if is_healthy else "unhealthy",
            "status_code": response.status_code,
            "response_time_ms": response.elapsed.total_seconds() * 1000,
            "healthy": is_healthy
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": service_name,
            "url": url,
            "status": "unhealthy",
            "error": str(e),
            "healthy": False
        }

def check_system_resources() -> dict:
    """Check system resource usage"""
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "system",
            "cpu_usage_percent": cpu_usage,
            "memory_usage_percent": memory_usage,
            "disk_usage_percent": disk_usage,
            "healthy": cpu_usage < 80 and memory_usage < 85 and disk_usage < 90
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "system",
            "error": str(e),
            "healthy": False
        }

def check_prometheus_metrics() -> dict:
    """Check Prometheus metrics endpoint"""
    try:
        response = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=5)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "prometheus",
            "url": f"{PROMETHEUS_URL}/-/healthy",
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "healthy": response.status_code == 200
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "prometheus",
            "error": str(e),
            "healthy": False
        }

def check_grafana() -> dict:
    """Check Grafana dashboard"""
    try:
        response = requests.get(f"{GRAFANA_URL}/api/health", timeout=5)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "grafana",
            "url": f"{GRAFANA_URL}/api/health",
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "healthy": response.status_code == 200
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "grafana",
            "error": str(e),
            "healthy": False
        }

def run_health_checks():
    """Run all health checks"""
    logger.info("Running health checks...")

    # Service health checks
    services = [
        ("edge-router", "http://edge-router:80/health"),
        ("availability-service", "http://availability-service:8000/health"),
        ("edge-ai-service", "http://edge-ai-service:8000/v2/health/ready"),
        ("redis-cache", "http://redis-cache:6379"),
        ("postgres-db", "http://postgres-db:5432"),
        ("prometheus", f"{PROMETHEUS_URL}/-/healthy"),
        ("grafana", f"{GRAFANA_URL}/api/health")
    ]

    results = []

    for service_name, url in services:
        result = check_service_health(service_name, url)
        results.append(result)
        log_to_file(result)
        logger.info(f"{service_name} status: {result['status']}")

    # System resource check
    system_result = check_system_resources()
    results.append(system_result)
    log_to_file(system_result)
    logger.info(f"System resources: CPU {system_result['cpu_usage_percent']}%, Memory {system_result['memory_usage_percent']}%")

    # Overall system health
    all_healthy = all(result['healthy'] for result in results)
    logger.info(f"Overall system health: {'HEALTHY' if all_healthy else 'UNHEALTHY'}")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "results": results,
        "overall_healthy": all_healthy
    }

def main():
    """Main health monitoring loop"""
    logger.info("Starting health monitoring service...")

    # Initial check
    run_health_checks()

    # Schedule periodic checks
    schedule.every(CHECK_INTERVAL).seconds.do(run_health_checks)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
