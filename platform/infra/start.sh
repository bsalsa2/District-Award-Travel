#!/bin/bash

# Build and start the Docker Compose stack
docker-compose up -d --build

# Check if the stack is up and running
if [ "$(docker-compose ps -q | wc -l)" -eq 4 ]; then
  echo "District Award Travel platform is up and running!"
else
  echo "Error starting the platform. Check the logs for more information."
  docker-compose logs
fi
