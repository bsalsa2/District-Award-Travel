#!/bin/bash
# Validation script for the alerting system

set -e

echo "Validating District Award Travel Alerting System..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running"
    exit 1
fi

# Check if required containers are up
REQUIRED_SERVICES=("district-alerting-service" "district-alerting-monitor" "district-alerting-dashboard")

for service in "${REQUIRED_SERVICES[@]}"; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        echo "ERROR: Service ${service} is not running"
        exit 1
    fi
done

# Check health status of alerting service
HEALTH_STATUS=$(curl -s http://localhost:8080/health | jq -r '.status')
if [ "$HEALTH_STATUS" != "healthy" ]; then
    echo "ERROR: Alerting service health check failed"
    exit 1
fi

# Check Prometheus metrics endpoint
if ! curl -s http://localhost:9090/metrics > /dev/null; then
    echo "ERROR: Prometheus metrics endpoint not responding"
    exit 1
fi

# Check Grafana dashboard
if ! curl -s http://localhost:3000/api/health > /dev/null; then
    echo "ERROR: Grafana dashboard not responding"
    exit 1
fi

# Test alert triggering
ALERT_RESPONSE=$(curl -s -X POST http://localhost:8080/alert \
    -H "Content-Type: application/json" \
    -d '{
        "type": "system_validation_test",
        "severity": "low",
        "message": "System validation test alert",
        "context": {"test": "true"}
    }')

if echo "$ALERT_RESPONSE" | grep -q "alert triggered"; then
    echo "SUCCESS: Alerting system is fully operational"
    echo "  - All services running"
    echo "  - Health checks passing"
    echo "  - Metrics collection working"
    echo "  - Grafana dashboard accessible"
    echo "  - Alert triggering functional"
    exit 0
else
    echo "ERROR: Alert triggering failed"
    exit 1
fi
