#!/bin/bash

# ==============================================================================
# Rollback Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/rollback.sh {dev|prod}
# ==============================================================================

set -e

ENV=$1

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/rollback.sh {dev|prod}"
    exit 1
fi

PROJECT_ROOT="/var/www/wvismis"
cd "$PROJECT_ROOT"

echo "======================================================"
echo "⚠️  EMERGENCY ROLLBACK - Environment: $ENV"
echo "======================================================"

CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
PREVIOUS_COMMIT=$(git rev-parse --short HEAD~1 2>/dev/null || echo "unknown")

echo "Current Commit:  $CURRENT_COMMIT"
echo "Target Rollback: $PREVIOUS_COMMIT"
echo "======================================================"

read -p "Are you sure you want to rollback to commit $PREVIOUS_COMMIT? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "🚫 Rollback cancelled."
    exit 0
fi

# 1. Checkout Previous Git Commit
echo "🔄 Checking out previous commit ($PREVIOUS_COMMIT)..."
git checkout HEAD~1

# 2. Restore Database from the latest backup before deployment
echo "💾 Restoring database from most recent backup..."
./deploy/restore-db.sh "$ENV"

# 3. Redeploy Backend
echo "🚀 Redeploying previous backend version..."
./deploy/backend-deploy.sh "$ENV"

# 4. Redeploy Frontend
echo "🚀 Redeploying previous frontend version..."
./deploy/frontend-deploy.sh "$ENV"

# 5. Run Health Check
echo "🏥 Validating system health after rollback..."
./deploy/health-check.sh "$ENV"

echo "======================================================"
echo "✅ Rollback completed successfully to commit $PREVIOUS_COMMIT!"
echo "======================================================"
