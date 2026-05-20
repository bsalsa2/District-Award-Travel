#!/bin/bash
set -euo pipefail

# District Award Travel - Daily Database Backup Script
# Runs as a cron job inside the backup container

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "💾 Starting daily database backup at $(date)"
echo "📁 Backup directory: $BACKUP_DIR"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL database
echo "🗄️  Backing up PostgreSQL database..."
docker exec dat_db pg_dump -U dat_user -d dat_db > "$BACKUP_DIR/dat_db_backup_$TIMESTAMP.sql"

# Backup Redis data
echo "📦 Backing up Redis data..."
docker exec dat_redis redis-cli --raw SAVE
docker cp dat_redis:/data/dump.rdb "$BACKUP_DIR/redis_dump_$TIMESTAMP.rdb"

# Compress old backups (keep last 30 days)
echo "🗜️  Compressing old backups..."
find "$BACKUP_DIR" -name "*.sql" -o -name "*.rdb" | while read -r file; do
    if [[ "$file" != *"_$TIMESTAMP"* ]]; then
        gzip -f "$file"
    fi
done

# Clean up backups older than 30 days
echo "🧹 Cleaning up backups older than 30 days..."
find "$BACKUP_DIR" -name "*.gz" -type f -mtime +30 -delete
find "$BACKUP_DIR" -name "*.sql" -type f -mtime +30 -delete
find "$BACKUP_DIR" -name "*.rdb" -type f -mtime +30 -delete

echo "✅ Daily backup completed successfully"
