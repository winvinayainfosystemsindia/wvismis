#!/bin/bash

# ==============================================================================
# Master One-Click Deployment Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/deploy-all.sh {dev|prod}
# ==============================================================================

set -e

ENV=$1

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/deploy-all.sh {dev|prod}"
    exit 1
fi

case $ENV in
    dev)
        DOMAIN="dev-mis.winvinaya.com"
        ;;
    prod)
        DOMAIN="mis.winvinaya.com"
        ;;
    *)
        echo "❌ Error: Invalid environment '$ENV'. Allowed: dev, prod"
        exit 1
        ;;
esac

PROJECT_ROOT="/var/www/wvismis"
cd "$PROJECT_ROOT"

echo "======================================================"
echo "🌟 Starting Full Automated Deployment - $ENV"
echo "Target Domain: https://$DOMAIN"
echo "Timestamp:     $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================"

# Step 1: Pre-deployment Database Backup
echo "📦 Step 1/4: Creating automated pre-deployment database backup..."
./deploy/backup-db.sh "$ENV"

# Step 2: Deploy Backend & Apply Database Migrations
echo "⚙️ Step 2/4: Deploying backend application & running migrations..."
./deploy/backend-deploy.sh "$ENV"

# Step 3: Build & Deploy Frontend
echo "🎨 Step 3/4: Building and publishing frontend application..."
./deploy/frontend-deploy.sh "$ENV"

# Step 4: Health Check & Verification
echo "🏥 Step 4/4: Executing comprehensive health checks..."
./deploy/health-check.sh "$ENV"

echo "======================================================"
echo "🎉 DEPLOYMENT SUCCEEDED!"
echo "Environment: $ENV"
echo "Application URL: https://$DOMAIN"
echo "API Docs:        https://$DOMAIN/docs"
echo "Health Check:    https://$DOMAIN/health"
echo "======================================================"
