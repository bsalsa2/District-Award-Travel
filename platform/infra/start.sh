#!/bin/bash
set -euo pipefail

# District Award Travel - Infrastructure Start Script
# This script launches the complete production infrastructure with a single command

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting District Award Travel Infrastructure..."
echo "📁 Project Root: $PROJECT_ROOT"
echo "📁 Script Directory: $SCRIPT_DIR"

# Create required directories
mkdir -p "$SCRIPT_DIR/certs" "$SCRIPT_DIR/backups" "$SCRIPT_DIR/logs"

# Generate self-signed cert if it doesn't exist (for development)
if [ ! -f "$SCRIPT_DIR/certs/server.crt" ]; then
    echo "🔐 Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SCRIPT_DIR/certs/server.key" \
        -out "$SCRIPT_DIR/certs/server.crt" \
        -subj "/C=US/ST=California/L=San Francisco/O=District Award Travel/CN=localhost"
fi

# Create htpasswd file for admin dashboard
if [ ! -f "$SCRIPT_DIR/.htpasswd" ]; then
    echo "🔒 Creating admin credentials..."
    htpasswd -bc "$SCRIPT_DIR/.htpasswd" admin "admin123"
fi

# Build and start all services
echo "🏗️ Building and starting services..."
docker-compose -f "$SCRIPT_DIR/docker-compose.yml" up -d --build

# Wait for services to be healthy
echo "⏳ Waiting for services to become healthy..."
for service in api db redis nginx backup; do
    echo "🔍 Checking $service health..."
    attempts=0
    max_attempts=30

    while [ $attempts -lt $max_attempts ]; do
        if docker-compose -f "$SCRIPT_DIR/docker-compose.yml" ps "$service" | grep -q "healthy"; then
            echo "✅ $service is healthy"
            break
        fi

        attempts=$((attempts + 1))
        sleep 2
    done

    if [ $attempts -eq $max_attempts ]; then
        echo "❌ $service failed to become healthy"
        docker-compose -f "$SCRIPT_DIR/docker-compose.yml" logs "$service"
        exit 1
    fi
done

# Display service information
echo ""
echo "🎉 District Award Travel Infrastructure is now running!"
echo ""
echo "📊 Service Status:"
docker-compose -f "$SCRIPT_DIR/docker-compose.yml" ps
echo ""
echo "🌐 Access Points:"
echo "  - Admin Dashboard: http://localhost/admin/ (user: admin, pass: admin123)"
echo "  - API: http://localhost/api/"
echo "  - Health Check: http://localhost/health"
echo ""
echo "📝 Logs are available in:"
echo "  - $SCRIPT_DIR/logs/"
echo ""
echo "🔧 To stop all services, run: docker-compose -f $SCRIPT_DIR/docker-compose.yml down"
echo "🔧 To view logs: docker-compose -f $SCRIPT_DIR/docker-compose.yml logs -f"
echo ""
