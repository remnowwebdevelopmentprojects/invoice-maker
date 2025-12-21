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
SERVICE_ACCOUNT="remnowinvoice-backup@remnow-invoice.iam.gserviceaccount.com"
PROJECT_ID="remnow-invoice"

# Set up PATH to include gcloud/gsutil if installed via snap
export PATH="/snap/bin:$PATH"

# If running as root, try to use the user's gcloud credentials
if [ "$(id -u)" -eq 0 ]; then
    # Try to find a user with gcloud credentials
    for user_dir in /home/*; do
        if [ -d "${user_dir}/.config/gcloud" ]; then
            export HOME="${user_dir}"
            export GOOGLE_APPLICATION_CREDENTIALS="${user_dir}/.config/gcloud/application_default_credentials.json"
            # Use the user's gcloud config
            export CLOUDSDK_CONFIG="${user_dir}/.config/gcloud"
            break
        fi
    done
fi

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
    
    # Ensure we're using the correct service account
    # Try to activate service account if gcloud is available
    if command -v gcloud &> /dev/null; then
        # Set the active account to the service account
        gcloud config set account ${SERVICE_ACCOUNT} 2>/dev/null || true
        gcloud config set project ${PROJECT_ID} 2>/dev/null || true
        
        # Activate service account (if running as root, use application-default credentials)
        if [ "$(id -u)" -eq 0 ]; then
            # For root user, try to use application-default credentials
            export GOOGLE_APPLICATION_CREDENTIALS="${HOME}/.config/gcloud/application_default_credentials.json" 2>/dev/null || true
        fi
    fi
    
    # Upload backup with error handling
    if gsutil cp ${BACKUP_FILE} gs://${GCS_BUCKET}/postgres-backups/ 2>&1; then
        echo "Backup uploaded successfully to Cloud Storage"
        
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
                echo "$BACKUP_LIST" | head -n $DELETE_COUNT | awk '{print $NF}' | xargs -r gsutil rm 2>/dev/null
                echo "Deleted $DELETE_COUNT old backup(s) from Cloud Storage"
            else
                echo "Only $BACKUP_COUNT backup(s) found, keeping all (retention: $RETENTION_DAYS days)"
            fi
        else
            echo "No backups found in Cloud Storage to clean up"
        fi
    else
        echo "ERROR: Failed to upload backup to Cloud Storage!"
        echo "Check authentication and permissions for service account: ${SERVICE_ACCOUNT}"
        exit 1
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
