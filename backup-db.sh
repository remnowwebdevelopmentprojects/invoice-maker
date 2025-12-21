#!/bin/bash
# PostgreSQL Backup Script for Remnowinvoice
# Uploads backups to Google Cloud Storage

set -e

# Configuration
DB_NAME="remnow_invoice"
DB_USER="postgres"
BACKUP_DIR="/opt/remnowinvoice/backups"
GCS_BUCKET="remnowinvoice-backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/remnowinvoice_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Change to docker-compose directory
cd /opt/remnowinvoice

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not found!"
    exit 1
fi

# Check if db service is running, if not try to start it
if ! docker compose ps db | grep -q "Up"; then
    echo "Database container is not running. Attempting to start..."
    docker compose up -d db
    
    # Wait for database to be ready
    echo "Waiting for database to be ready..."
    sleep 10
    
    # Check again
    if ! docker compose ps db | grep -q "Up"; then
        echo "ERROR: Failed to start database container!"
        docker compose logs db
        exit 1
    fi
fi

# Create backup using docker compose exec (using service name 'db')
echo "Creating database backup..."
docker compose exec -T db pg_dump -U ${DB_USER} -d ${DB_NAME} | gzip > ${BACKUP_FILE}

# Check if backup was created successfully
if [ ! -f "${BACKUP_FILE}" ] || [ ! -s "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file was not created or is empty!"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup created successfully: ${BACKUP_SIZE}"

# Upload to Google Cloud Storage
if command -v gsutil &> /dev/null; then
    echo "Uploading backup to Cloud Storage..."
    gsutil cp ${BACKUP_FILE} gs://${GCS_BUCKET}/postgres-backups/
    
    # Clean up old backups from GCS (keep last 30 days)
    echo "Cleaning up old backups from Cloud Storage..."
    # Get list of backups sorted by date (oldest first)
    BACKUP_LIST=$(gsutil ls -l gs://${GCS_BUCKET}/postgres-backups/*.sql.gz 2>/dev/null | \
        grep -E "\.sql\.gz$" | \
        sort -k2)
    
    if [ -n "$BACKUP_LIST" ]; then
        BACKUP_COUNT=$(echo "$BACKUP_LIST" | wc -l)
        if [ $BACKUP_COUNT -gt $RETENTION_DAYS ]; then
            DELETE_COUNT=$((BACKUP_COUNT - RETENTION_DAYS))
            echo "$BACKUP_LIST" | head -n $DELETE_COUNT | awk '{print $NF}' | xargs gsutil rm
            echo "Deleted $DELETE_COUNT old backup(s) from Cloud Storage"
        else
            echo "Only $BACKUP_COUNT backup(s) found, keeping all (retention: $RETENTION_DAYS days)"
        fi
    else
        echo "No backups found in Cloud Storage to clean up"
    fi
else
    echo "WARNING: gsutil not found. Skipping Cloud Storage upload."
fi

# Clean up local backups older than retention period
echo "Cleaning up local backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=$(find ${BACKUP_DIR} -name "*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete -print | wc -l)
if [ $DELETED_COUNT -gt 0 ]; then
    echo "Deleted $DELETED_COUNT old local backup(s)"
else
    echo "No old local backups to delete"
fi

echo "Backup completed successfully: ${BACKUP_FILE}"
