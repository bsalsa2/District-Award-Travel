#!/bin/bash
set -e

echo "Stopping Alert Escalation System..."
docker-compose down -v

echo "System stopped successfully!"
