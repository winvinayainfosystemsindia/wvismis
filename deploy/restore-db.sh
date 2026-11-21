#!/bin/bash

# ==============================================================================
# Database Restore Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/restore-db.sh {dev|prod} [optional_backup_file.sql.gz]
# ==============================================================================

set -e

ENV=$1
SPECIFIC_FILE=$2

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/restore-db.sh {dev|prod} [optional_backup_file.sql.gz]"
    exit 1
fi

case $ENV in
    dev)
        DB_NAME="wvismis_dev"
        ;;
    prod)
        DB_NAME="wvismis_prod"
        ;;
    *)
        echo "❌ Error: Invalid environment '$ENV'. Allowed: dev, prod"
        exit 1
        ;;
esac

BACKUP_DIR="/var/www/wvismis/backups/db"

if [ -n "$SPECIFIC_FILE" ]; then
    RESTORE_FILE="$SPECIFIC_FILE"
else
    # Find latest backup
    RESTORE_FILE=$(ls -t "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null | head -n 1)
fi

if [ -z "$RESTORE_FILE" ] || [ ! -f "$RESTORE_FILE" ]; then
    echo "❌ Error: No backup file found to restore: $RESTORE_FILE"
    exit 1
fi

echo "======================================================"
echo "⚠️  DATABASE RESTORE WARNING - $ENV"
echo "Target Database: $DB_NAME"
echo "Source File:     $RESTORE_FILE"
echo "======================================================"
echo "This will OVERWRITE all data in $DB_NAME with the backup file."
read -p "Type 'YES' to confirm restore: " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo "🚫 Database restore cancelled by user."
    exit 0
fi

echo "⏳ Terminating existing database connections..."
sudo -u postgres psql -c "
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$DB_NAME'
  AND pid <> pg_backend_pid();
" || true

echo "⏳ Restoring database from backup..."
gunzip -c "$RESTORE_FILE" | sudo -u postgres psql -d "$DB_NAME"

echo "======================================================"
echo "✅ Database restore completed successfully for $DB_NAME!"
echo "======================================================"
