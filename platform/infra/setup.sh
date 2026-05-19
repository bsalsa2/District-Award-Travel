#!/bin/bash

# Create directories for volumes
mkdir -p platform/infra/prometheus
mkdir -p platform/infra/grafana

# Start Docker Compose
docker-compose up -d
