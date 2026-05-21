#!/bin/bash

# Build and deploy the application
docker-compose build
docker-compose up -d

# Verify the deployment
docker-compose ps
