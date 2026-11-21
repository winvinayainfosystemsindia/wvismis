#!/bin/bash

# ==============================================================================
# SSL Setup Script via Let's Encrypt Certbot for WinVinaya MIS (WVISMIS)
# Usage: sudo ./deploy/setup-ssl.sh {dev|prod|both}
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run as root or with sudo:"
    echo "sudo ./deploy/setup-ssl.sh {dev|prod|both}"
    exit 1
fi

TARGET=$1

if [ -z "$TARGET" ]; then
    echo "❌ Error: Target not specified."
    echo "Usage: sudo ./deploy/setup-ssl.sh {dev|prod|both}"
    exit 1
fi

EMAIL="admin@winvinaya.com"

echo "======================================================"
echo "🔒 Setting Up Free SSL Certificate via Let's Encrypt"
echo "Target: $TARGET"
echo "Certbot Contact Email: $EMAIL"
echo "======================================================"

case $TARGET in
    dev)
        echo "Obtaining SSL for dev-mis.winvinaya.com..."
        certbot --nginx \
            -d dev-mis.winvinaya.com \
            --non-interactive \
            --agree-tos \
            --email "$EMAIL" \
            --redirect
        ;;
    prod)
        echo "Obtaining SSL for mis.winvinaya.com and www.mis.winvinaya.com..."
        certbot --nginx \
            -d mis.winvinaya.com \
            -d www.mis.winvinaya.com \
            --non-interactive \
            --agree-tos \
            --email "$EMAIL" \
            --redirect
        ;;
    both)
        echo "Obtaining SSL for all WinVinaya MIS domains..."
        certbot --nginx \
            -d dev-mis.winvinaya.com \
            --non-interactive \
            --agree-tos \
            --email "$EMAIL" \
            --redirect

        certbot --nginx \
            -d mis.winvinaya.com \
            -d www.mis.winvinaya.com \
            --non-interactive \
            --agree-tos \
            --email "$EMAIL" \
            --redirect
        ;;
    *)
        echo "❌ Error: Invalid target '$TARGET'. Allowed: dev, prod, both"
        exit 1
        ;;
esac

echo "Testing automated renewal..."
certbot renew --dry-run

echo "Reloading Nginx with new certificates..."
nginx -t && systemctl reload nginx

echo "======================================================"
echo "🎉 SSL Setup and Automated Renewal Configured!"
echo "======================================================"
