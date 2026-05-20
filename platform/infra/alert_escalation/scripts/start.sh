#!/bin/bash
set -e

# Ensure directories exist
mkdir -p /app/logs
mkdir -p /app/config

# Copy example config if not exists
if [ ! -f /app/.env ]; then
    cp /app/.env.example /app/.env
    echo "Created .env file from example. Please configure it."
    exit 1
fi

# Start the services
echo "Starting Alert Escalation System..."
docker-compose up -d --build

echo "System started successfully!"
echo "API available at: http://localhost:8000"
echo "Prometheus at: http://localhost:9091"
echo "Grafana at: http://localhost:3000"
