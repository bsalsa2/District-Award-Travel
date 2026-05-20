#!/bin/bash
# Health check script for the alerting service container

set -e

# Check if the service is responding to health checks
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health | grep -q "200"; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed"
    exit 1
fi
