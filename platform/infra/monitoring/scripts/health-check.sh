#!/bin/bash
set -euo pipefail

# Monitoring system health check script
# Checks all components of the monitoring stack

echo "🔍 Checking monitoring system health..."

# Check Prometheus
if curl -s http://localhost:9090/-/healthy > /dev/null; then
    echo "✅ Prometheus is healthy"
else
    echo "❌ Prometheus is unhealthy"
    exit 1
fi

# Check Grafana
if curl -s http://localhost:3000/api/health > /dev/null; then
    echo "✅ Grafana is healthy"
else
    echo "❌ Grafana is unhealthy"
    exit 1
fi

# Check Alertmanager
if curl -s http://localhost:9093/-/healthy > /dev/null; then
    echo "✅ Alertmanager is healthy"
else
    echo "❌ Alertmanager is unhealthy"
    exit 1
fi

# Check Node Exporter
if curl -s http://localhost:9100/metrics > /dev/null; then
    echo "✅ Node Exporter is healthy"
else
    echo "❌ Node Exporter is unhealthy"
    exit 1
fi

# Check Blackbox Exporter
if curl -s http://localhost:9115/-/healthy > /dev/null; then
    echo "✅ Blackbox Exporter is healthy"
else
    echo "❌ Blackbox Exporter is unhealthy"
    exit 1
fi

# Check Pushgateway
if curl -s http://localhost:9091/-/healthy > /dev/null; then
    echo "✅ Pushgateway is healthy"
else
    echo "❌ Pushgateway is unhealthy"
    exit 1
fi

# Check Mailhog
if curl -s http://localhost:8025 > /dev/null; then
    echo "✅ Mailhog is healthy"
else
    echo "❌ Mailhog is unhealthy"
    exit 1
fi

echo "🎉 All monitoring components are healthy!"
exit 0
