# Setup cron job for database backups
chmod +x /opt/remnowinvoice/backup-db.sh

(crontab -l 2>/dev/null; echo "0 2 * * * /opt/remnowinvoice/backup-db.sh >> /var/log/remnowinvoice-backup.log 2>&1") | crontab -

echo "Cron job configured for daily backups at 2 AM"