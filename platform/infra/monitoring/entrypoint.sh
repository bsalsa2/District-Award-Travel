#!/bin/bash
set -e

echo "Starting Award Space Monitoring System..."

# Wait for dependencies
echo "Waiting for database directory..."
while [ ! -d "/data" ]; do
  sleep 1
done

echo "Starting monitoring service..."
exec python /app/monitoring.py
