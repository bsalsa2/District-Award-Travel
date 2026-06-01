#!/bin/bash

# Add a cron job to run the healthcheck script every 5 minutes
(crontab -l ; echo "*/5 * * * * /platform/infra/kubernetes/healthcheck.sh") | crontab -

# Add a cron job to run the autoscale script every hour
(crontab -l ; echo "0 * * * * /platform/infra/kubernetes/autoscale.sh") | crontab -
