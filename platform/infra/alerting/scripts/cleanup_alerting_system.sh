#!/bin/bash
# Cleanup script for the alerting system

set -e

echo "Cleaning up District Award Travel Alerting System..."

# Stop and remove containers
echo "Stopping and removing containers..."
docker-compose -f docker-compose.yml down -v

# Remove volumes
echo "Removing volumes..."
docker volume prune -f

# Remove networks
echo "Removing networks..."
docker network prune -f

# Clean up log files
echo "Cleaning up log files..."
rm -rf /var/log/alerting/*
rm -rf ./logs/*
rm -rf ./prometheus-data/*
rm -rf ./grafana-data/*

echo "Cleanup complete!"
