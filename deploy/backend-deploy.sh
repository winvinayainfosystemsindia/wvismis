#!/bin/bash

# ==============================================================================
# Backend Deployment Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/backend-deploy.sh {dev|prod}
# ==============================================================================

set -e  # Exit immediately if a command exits with a non-zero status

ENV=$1

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/backend-deploy.sh {dev|prod}"
    exit 1
fi

APP_DIR="/var/www/wvismis/backend"

# Environment-specific configuration
case $ENV in
    dev)
        PORT=8000
        APP_NAME="wvismis-backend-dev"
        ENV_FILE="$APP_DIR/.env.dev"
        ;;
    prod)
        PORT=8002
        APP_NAME="wvismis-backend-prod"
        ENV_FILE="$APP_DIR/.env.prod"
        ;;
    *)
        echo "❌ Error: Invalid environment '$ENV'. Allowed: dev, prod"
        exit 1
        ;;
esac

echo "======================================================"
echo "🚀 Deploying Backend - Environment: $ENV"
echo "Process Name: $APP_NAME"
echo "Internal Port: $PORT"
echo "Directory:     $APP_DIR"
echo "Env File:      $ENV_FILE"
echo "======================================================"

cd "$APP_DIR"

# 1. Stop existing PM2 process safely
echo "🛑 Stopping existing PM2 process if active..."
pm2 stop "$APP_NAME" || true
pm2 delete "$APP_NAME" || true

# 2. Virtual Environment Setup
VENV_NAME="venv-$ENV"
if [ ! -d "$VENV_NAME" ]; then
    echo "🐍 Creating virtual environment ($VENV_NAME)..."
    python3.11 -m venv "$VENV_NAME"
fi

echo "🔌 Activating virtual environment ($VENV_NAME)..."
source "$VENV_NAME/bin/activate"

# 3. Pip and dependencies install
echo "⬆️ Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo "📦 Installing Python requirements..."
pip install -r requirements.txt

# 4. Verify Environment File
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: Environment file '$ENV_FILE' not found!"
    echo "Please copy backend/.env.$ENV.example to $ENV_FILE and configure credentials."
    exit 1
fi

# 5. Database Migrations via Alembic
echo "🗄️ Running database migrations..."
set -a
# Source the env file cleanly (stripping comments and Windows CRLF)
source <(grep -v '^#' "$ENV_FILE" | grep -v '^$' | sed 's/\r$//')
set +a

# Run alembic head migration
alembic upgrade head

# 6. Start Application with PM2
echo "▶️ Starting FastAPI backend with PM2 ($APP_NAME on port $PORT)..."
pm2 start "$VENV_NAME/bin/uvicorn" \
    --name "$APP_NAME" \
    --interpreter none \
    --max-memory-restart 500M \
    -- app.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --env-file "$ENV_FILE"

# 7. Persist PM2 configuration
echo "💾 Persisting PM2 startup list..."
pm2 save

echo "======================================================"
echo "✅ Backend successfully deployed for $ENV!"
echo "Status:"
pm2 status "$APP_NAME"
echo "======================================================"
