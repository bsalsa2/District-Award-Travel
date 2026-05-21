#!/bin/bash

# Check the health of the services
docker-compose exec nginx curl -s -f http://localhost:80
docker-compose exec aws-lambda curl -s -f http://localhost:8080
docker-compose exec google-cloud-functions curl -s -f http://localhost:8081
docker-compose exec azure-functions curl -s -f http://localhost:8082
