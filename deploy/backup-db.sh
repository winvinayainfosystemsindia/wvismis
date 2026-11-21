#!/bin/bash

# ==============================================================================
# Database Backup Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/backup-db.sh {dev|prod}
# ==============================================================================

set -e

ENV=$1

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/backup-db.sh {dev|prod}"
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
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "======================================================"
echo "💾 Database Backup - Environment: $ENV"
echo "Target Database: $DB_NAME"
echo "Destination:     $BACKUP_FILE"
echo "======================================================"

# Run pg_dump with compression
echo "⏳ Exporting PostgreSQL database..."
if sudo -u postgres pg_dump -d "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup created successfully: $BACKUP_FILE ($FILE_SIZE)"
else
    echo "❌ Error: Database backup failed!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Rotate backups: retain last 14 backups
echo "🧹 Rotating old backups (retaining latest 14)..."
cd "$BACKUP_DIR"
ls -t "${DB_NAME}"_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f || true

echo "======================================================"
echo "✅ Database backup complete!"
echo "Recent backups in $BACKUP_DIR:"
ls -lht "${DB_NAME}"_*.sql.gz | head -n 5
echo "======================================================"
