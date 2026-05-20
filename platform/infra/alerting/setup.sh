#!/bin/bash
set -e

# Create necessary directories
mkdir -p alertmanager/data
mkdir -p notification-service/logs
mkdir -p notification-worker/logs

# Set permissions
chmod -R 755 alertmanager
chmod -R 755 notification-service
chmod -R 755 notification-worker

# Copy environment template if .env doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please configure your environment variables."
fi

echo "Alerting system setup complete!"
echo "Start the system with: docker-compose up -d"
