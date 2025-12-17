
# Uploads backups to Google Cloud Storage
set -e

DB_NAME="remnow_invoice"
DB_USER="postgres"
BACKUP_DIR="/opt/remnowinvoice/backups"
GCS_BUCKET="remnowinvoice-backups"  
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/remnowinvoice_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30

mkdir -p ${BACKUP_DIR}

echo "Creating database backup..."
PGPASSWORD="${POSTGRES_PASSWORD:-12345}" pg_dump -h localhost -U ${DB_USER} -d ${DB_NAME} | gzip > ${BACKUP_FILE}

if command -v gsutil &> /dev/null; then
    echo "Uploading backup to Cloud Storage..."
    gsutil cp ${BACKUP_FILE} gs://${GCS_BUCKET}/postgres-backups/
    
    echo "Cleaning up old backups from Cloud Storage..."
    gsutil -m rm -r gs://${GCS_BUCKET}/postgres-backups/* 2>/dev/null || true
    gsutil ls -l gs://${GCS_BUCKET}/postgres-backups/ | awk '{if ($1 < cutoff) print $NF}' | xargs -r gsutil rm || true
fi

echo "Cleaning up local backups older than ${RETENTION_DAYS} days..."
find ${BACKUP_DIR} -name "*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: ${BACKUP_FILE}"