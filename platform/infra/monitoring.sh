#!/bin/bash

# Start Docker Compose
docker-compose up -d

# Check if Prometheus is running
if ! curl -s http://localhost:9090 > /dev/null; then
  echo "Prometheus is not running"
  exit 1
fi

# Check if Grafana is running
if ! curl -s http://localhost:3000 > /dev/null; then
  echo "Grafana is not running"
  exit 1
fi

# Check if Node Exporter is running
if ! curl -s http://localhost:9100 > /dev/null; then
  echo "Node Exporter is not running"
  exit 1
fi

# Check if Alertmanager is running
if ! curl -s http://localhost:9093 > /dev/null; then
  echo "Alertmanager is not running"
  exit 1
fi
