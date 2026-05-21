#!/bin/bash
# Chaos Monkey Setup Script

set -e

echo "=== Chaos Monkey Setup ==="

# Create directory structure
echo "Creating directory structure..."
mkdir -p /app/{config,logs,scripts}
mkdir -p /app/config/scenarios
mkdir -p /app/logs

# Copy configuration files
echo "Copying configuration files..."
cp -r ./chaos-monkey/config/* /app/config/
cp ./chaos-monkey/scripts/* /app/scripts/

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --no-cache-dir -r /app/requirements.txt

# Set permissions
echo "Setting permissions..."
chmod -R 755 /app
chown -R nobody:nogroup /app

# Create log files
touch /app/logs/chaos-monkey.log
chown nobody:nogroup /app/logs/chaos-monkey.log

echo "=== Chaos Monkey Setup Complete ==="
