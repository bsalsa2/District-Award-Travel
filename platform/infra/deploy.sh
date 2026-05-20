#!/bin/bash
set -euo pipefail

# District Award Travel - Automated Deployment Script
# Handles deployment, updates, and rollbacks

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$SCRIPT_DIR/backups/deploy_$TIMESTAMP"

echo "🚀 Starting District Award Travel Deployment..."
echo "📁 Project Root: $PROJECT_ROOT"
echo "📁 Script Directory: $SCRIPT_DIR"
echo "📅 Timestamp: $TIMESTAMP"

# Function to create backup
create_backup() {
    echo "💾 Creating backup of current state..."

    # Backup database
    echo "🗄️  Backing up PostgreSQL database..."
    docker exec dat_db pg_dump -U dat_user -d dat_db > "$BACKUP_DIR/dat_db_backup_$TIMESTAMP.sql"

    # Backup Redis data
    echo "📦 Backing up Redis data..."
    docker exec dat_redis redis-cli --raw SAVE
    docker cp dat_redis:/data/dump.rdb "$BACKUP_DIR/redis_dump_$TIMESTAMP.rdb"

    # Backup volumes if they exist
    if docker volume inspect dat_postgres_data >/dev/null 2>&1; then
        docker run --rm -v dat_postgres_data:/volume -v "$BACKUP_DIR":/backup alpine \
            tar cvf /backup/postgres_data_$TIMESTAMP.tar /volume
    fi

    echo "✅ Backup created at: $BACKUP_DIR"
}

# Function to update services
update_services() {
    echo "🔄 Updating services..."

    # Pull latest images
    echo "📥 Pulling latest images..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.yml" pull

    # Rebuild and restart services
    echo "🏗️  Rebuilding and restarting services..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.yml" up -d --build

    # Wait for services to be healthy
    echo "⏳ Waiting for services to become healthy..."
    for service in api db redis nginx; do
        echo "🔍 Checking $service health..."
        attempts=0
        max_attempts=30

        while [ $attempts -lt $max_attempts ]; do
            if docker-compose -f "$SCRIPT_DIR/docker-compose.yml" ps "$service" | grep -q "healthy"; then
                echo "✅ $service is healthy"
                break
            fi

            attempts=$((attempts + 1))
            sleep 2
        done

        if [ $attempts -eq $max_attempts ]; then
            echo "❌ $service failed to become healthy"
            echo "🔄 Attempting rollback..."
            rollback_deployment
            exit 1
        fi
    done
}

# Function to rollback deployment
rollback_deployment() {
    echo "🔙 Rolling back to previous version..."

    if [ -d "$BACKUP_DIR" ]; then
        # Restore database
        if [ -f "$BACKUP_DIR/dat_db_backup_$TIMESTAMP.sql" ]; then
            echo "🗄️  Restoring PostgreSQL database..."
            docker exec -i dat_db psql -U dat_user -d dat_db < "$BACKUP_DIR/dat_db_backup_$TIMESTAMP.sql"
        fi

        # Restore Redis
        if [ -f "$BACKUP_DIR/redis_dump_$TIMESTAMP.rdb" ]; then
            echo "📦 Restoring Redis data..."
            docker cp "$BACKUP_DIR/redis_dump_$TIMESTAMP.rdb" dat_redis:/data/dump.rdb
            docker exec dat_redis redis-cli shutdown save
            docker restart dat_redis
        fi

        echo "✅ Rollback completed"
    else
        echo "⚠️  No backup found for rollback"
    fi
}

# Function to run database migrations
run_migrations() {
    echo "🔄 Running database migrations..."

    # Wait for database to be ready
    attempts=0
    max_attempts=30

    while [ $attempts -lt $max_attempts ]; do
        if docker-compose -f "$SCRIPT_DIR/docker-compose.yml" exec db pg_isready -U dat_user -d dat_db >/dev/null 2>&1; then
            break
        fi

        attempts=$((attempts + 1))
        sleep 2
    done

    if [ $attempts -eq $max_attempts ]; then
        echo "❌ Database failed to become ready for migrations"
        exit 1
    fi

    # Run migrations
    docker-compose -f "$SCRIPT_DIR/docker-compose.yml" exec api python -m alembic upgrade head
    echo "✅ Database migrations completed"
}

# Main deployment logic
main() {
    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    # Create backup before deployment
    create_backup

    # Update services
    update_services

    # Run migrations
    run_migrations

    # Clean up old backups (keep last 7 days)
    echo "🧹 Cleaning up old backups..."
    find "$SCRIPT_DIR/backups" -name "deploy_*" -type d -mtime +7 -exec rm -rf {} \;

    echo ""
    echo "🎉 Deployment completed successfully!"
    echo "📊 New service status:"
    docker-compose -f "$SCRIPT_DIR/docker-compose.yml" ps
    echo ""
}

# Execute main function
main
