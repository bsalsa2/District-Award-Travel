#!/bin/bash

# Start the Docker Compose stack
docker-compose up -d

# Verify the services are running
docker-compose ps

# Verify the health of the services
docker-compose exec monitoring-dashboard curl --fail http://localhost:80/
docker-compose exec prometheus curl --fail http://localhost:9090/
docker-compose exec grafana curl --fail http://localhost:3000/
