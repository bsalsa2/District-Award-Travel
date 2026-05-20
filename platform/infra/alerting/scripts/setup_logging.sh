#!/bin/bash
# Setup script for alerting system logging infrastructure

set -e

echo "Setting up logging infrastructure for District Award Travel alerting system..."

# Create necessary directories
mkdir -p /var/log/alerting
mkdir -p /etc/alerting
mkdir -p /var/run/alerting

# Set permissions
chown -R 1000:1000 /var/log/alerting
chmod -R 755 /var/log/alerting

# Create log files with proper permissions
touch /var/log/alerting/alerting-service.log
chown 1000:1000 /var/log/alerting/alerting-service.log
chmod 644 /var/log/alerting/alerting-service.log

# Create log rotation configuration
cat > /etc/alerting/logrotate.conf << 'EOF'
/var/log/alerting/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        /usr/bin/killall -SIGUSR1 python 2>/dev/null || true
    endscript
}
EOF

# Install logrotate if not present
if ! command -v logrotate &> /dev/null; then
    apt-get update && apt-get install -y logrotate
fi

# Create systemd service for log rotation
cat > /etc/systemd/system/alerting-logrotate.service << 'EOF'
[Unit]
Description=Alerting System Log Rotation
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/logrotate -f /etc/alerting/logrotate.conf
User=root

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer for log rotation
cat > /etc/systemd/system/alerting-logrotate.timer << 'EOF'
[Unit]
Description=Run Alerting System Log Rotation Daily

[Timer]
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start the timer
systemctl daemon-reload
systemctl enable alerting-logrotate.timer
systemctl start alerting-logrotate.timer

# Create monitoring script
cat > /usr/local/bin/monitor-alerting-logs.sh << 'EOF'
#!/bin/bash
# Monitor alerting system logs for errors and warnings

LOG_FILE="/var/log/alerting/alerting-service.log"
ERROR_COUNT=$(grep -c "ERROR" "$LOG_FILE" || echo 0)
WARN_COUNT=$(grep -c "WARNING" "$LOG_FILE" || echo 0)
CRITICAL_COUNT=$(grep -c "CRITICAL" "$LOG_FILE" || echo 0)

# Send alert if error count exceeds threshold
if [ "$ERROR_COUNT" -gt 10 ]; then
    echo "ALERT: High error count in alerting system logs: $ERROR_COUNT errors" | \
    curl -X POST http://localhost:8080/alert \
    -H "Content-Type: application/json" \
    -d "{
        \"type\": \"log_error_threshold_exceeded\",
        \"severity\": \"high\",
        \"message\": \"High error count in alerting system logs\",
        \"context\": {
            \"error_count\": $ERROR_COUNT,
            \"log_file\": \"$LOG_FILE\"
        }
    }"
fi

# Log summary
echo "Log monitoring completed: Errors=$ERROR_COUNT, Warnings=$WARN_COUNT, Critical=$CRITICAL_COUNT"
EOF

chmod +x /usr/local/bin/monitor-alerting-logs.sh

# Create cron job for log monitoring
cat > /etc/cron.d/alerting-log-monitor << 'EOF'
*/5 * * * * root /usr/local/bin/monitor-alerting-logs.sh >> /var/log/alerting/log-monitor.log 2>&1
EOF

echo "Logging infrastructure setup complete!"
