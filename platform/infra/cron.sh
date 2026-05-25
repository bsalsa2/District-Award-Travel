#!/bin/bash

# Run AI-powered testing every hour
0 * * * * docker-compose exec ai-tester python ai_tester.py
