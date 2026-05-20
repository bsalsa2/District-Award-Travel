#!/bin/bash

curl -s -f http://localhost:8080 > /dev/null
if [ $? -eq 0 ]; then
    echo "Award travel booking system is up and running"
else
    echo "Award travel booking system is down"
fi
