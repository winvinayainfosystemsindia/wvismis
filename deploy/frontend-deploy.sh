#!/bin/bash

# ==============================================================================
# Frontend Deployment Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/frontend-deploy.sh {dev|prod}
# ==============================================================================

set -e  # Exit on error

ENV=$1

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/frontend-deploy.sh {dev|prod}"
    exit 1
fi

FRONTEND_DIR="/var/www/wvismis/frontend"

# Environment-specific directories & env files
case $ENV in
    dev)
        DEPLOY_DIR="$FRONTEND_DIR/dist-dev"
        ENV_FILE=".env.dev"
        DOMAIN="dev-mis.winvinaya.com"
        ;;
    prod)
        DEPLOY_DIR="$FRONTEND_DIR/dist-prod"
        ENV_FILE=".env.prod"
        DOMAIN="mis.winvinaya.com"
        ;;
    *)
        echo "❌ Error: Invalid environment '$ENV'. Allowed: dev, prod"
        exit 1
        ;;
esac

echo "======================================================"
echo "🚀 Deploying Frontend - Environment: $ENV"
echo "Target Domain:    $DOMAIN"
echo "Deploy Directory: $DEPLOY_DIR"
echo "Environment File: $ENV_FILE"
echo "======================================================"

cd "$FRONTEND_DIR"

# 1. Install / update Node dependencies
echo "📦 Installing frontend dependencies..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

# 2. Check and copy environment file
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: Frontend environment file '$ENV_FILE' not found!"
    echo "Please create $FRONTEND_DIR/$ENV_FILE with appropriate VITE_API_URL."
    exit 1
fi

echo "📄 Copying $ENV_FILE to active .env for Vite build..."
cp "$ENV_FILE" .env

# 3. Build React Application with expanded V8 Heap (prevents OOM on EC2)
echo "🔨 Building React + Vite production bundle..."
NODE_OPTIONS="--max-old-space-size=3072" npm run build

# 4. Atomic Deployment with backup
mkdir -p "$DEPLOY_DIR"

if [ -d "$DEPLOY_DIR/assets" ]; then
    echo "💾 Backing up previous build..."
    rm -rf "${DEPLOY_DIR}.backup"
    cp -r "$DEPLOY_DIR" "${DEPLOY_DIR}.backup"
fi

echo "🧹 Clearing old build artifacts..."
rm -rf "$DEPLOY_DIR"/*

echo "📂 Publishing new build to $DEPLOY_DIR..."
cp -r dist/* "$DEPLOY_DIR/"

# 5. Set proper web server permissions
echo "🔒 Setting file permissions (755)..."
chmod -R 755 "$DEPLOY_DIR"

# 6. Test and Reload Nginx
echo "🔄 Reloading Nginx..."
sudo nginx -t && sudo systemctl reload nginx

echo "======================================================"
echo "✅ Frontend successfully deployed for $ENV!"
echo "Served from: $DEPLOY_DIR"
echo "Domain:      https://$DOMAIN"
echo "======================================================"

ls -lah "$DEPLOY_DIR" | head -n 10
