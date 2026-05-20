#!/bin/bash
# Deployment script for the alerting system

set -e

echo "Deploying District Award Travel Alerting System..."

# Navigate to alerting directory
cd "$(dirname "$0")/.."

# Build and start the services
echo "Building and starting alerting services..."
docker-compose -f docker-compose.yml build --no-cache
docker-compose -f docker-compose.yml up -d

# Wait for services to be ready
echo "Waiting for services to initialize..."
sleep 30

# Run validation
echo "Running system validation..."
./scripts/validate_alerting_system.sh

if [ $? -eq 0 ]; then
    echo "Deployment successful!"
    echo "Alerting system is now available at:"
    echo "  - API: http://localhost:8080"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
    echo ""
    echo "To access logs:"
    echo "  - Alerting service: /var/log/alerting/alerting-service.log"
    echo "  - System logs: docker logs district-alerting-service"
else
    echo "Deployment failed! Check logs for details."
    exit 1
fi
