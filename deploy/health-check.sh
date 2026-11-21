#!/bin/bash

# ==============================================================================
# Health Check Script for WinVinaya MIS (WVISMIS)
# Usage: ./deploy/health-check.sh {dev|prod}
# ==============================================================================

set -e

ENV=$1

if [ -z "$ENV" ]; then
    echo "❌ Error: Environment not specified."
    echo "Usage: ./deploy/health-check.sh {dev|prod}"
    exit 1
fi

case $ENV in
    dev)
        BACKEND_PORT=8000
        APP_NAME="wvismis-backend-dev"
        DOMAIN="dev-mis.winvinaya.com"
        API_URL="http://127.0.0.1:8000"
        ;;
    prod)
        BACKEND_PORT=8002
        APP_NAME="wvismis-backend-prod"
        DOMAIN="mis.winvinaya.com"
        API_URL="http://127.0.0.1:8002"
        ;;
    *)
        echo "❌ Error: Invalid environment '$ENV'. Allowed: dev, prod"
        exit 1
        ;;
esac

echo "======================================================"
echo "🏥 Performing Health Check - Environment: $ENV"
echo "Domain:   $DOMAIN"
echo "Backend:  $API_URL"
echo "PM2 App:  $APP_NAME"
echo "======================================================"

# 1. Check PM2 Process Status
echo "🔍 1/4 Checking PM2 process ($APP_NAME)..."
if command -v pm2 &> /dev/null; then
    PM2_STATUS=$(pm2 jlist | jq -r ".[] | select(.name == \"$APP_NAME\") | .pm2_env.status")
    if [ "$PM2_STATUS" == "online" ]; then
        echo "✅ PM2 process is ONLINE."
    else
        echo "❌ PM2 process is NOT online. Current status: $PM2_STATUS"
        pm2 logs "$APP_NAME" --lines 20 --nostream || true
        exit 1
    fi
else
    echo "⚠️  PM2 not found in PATH; skipping PM2 check."
fi

# 2. Check Backend Health Endpoint
echo "🔍 2/4 Checking FastAPI /health endpoint..."
HEALTH_RES=$(curl -s -w "\n%{http_code}" "$API_URL/health" || echo "FAILED\n000")
HTTP_CODE=$(echo "$HEALTH_RES" | tail -n1)
BODY=$(echo "$HEALTH_RES" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Backend HTTP Health check returned 200 OK."
    echo "   Response: $BODY"
else
    echo "❌ Backend health check failed with HTTP code $HTTP_CODE!"
    echo "   Response: $BODY"
    exit 1
fi

# 3. Check Database Connection via Health Endpoint
echo "🔍 3/4 Verifying PostgreSQL database status..."
if echo "$BODY" | grep -q '"operational"'; then
    echo "✅ Database connection is operational."
else
    echo "⚠️  Warning: Database health check did not explicitly report operational."
fi

# 4. Check Frontend Web Server / Nginx
echo "🔍 4/4 Verifying local Nginx response for $DOMAIN..."
NGINX_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: $DOMAIN" http://127.0.0.1/ || echo "000")
if [ "$NGINX_CODE" -eq 200 ] || [ "$NGINX_CODE" -eq 301 ] || [ "$NGINX_CODE" -eq 302 ]; then
    echo "✅ Nginx is serving frontend for $DOMAIN (HTTP $NGINX_CODE)."
else
    echo "⚠️  Nginx returned HTTP $NGINX_CODE for host $DOMAIN. Check Nginx site configs."
fi

echo "======================================================"
echo "🎉 All health checks passed successfully for $ENV!"
echo "======================================================"
