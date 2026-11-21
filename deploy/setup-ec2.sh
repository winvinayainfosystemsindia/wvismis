#!/bin/bash

# ==============================================================================
# EC2 Initial Server Setup Script for WinVinaya MIS (WVISMIS)
# OS Supported: Ubuntu 22.04 LTS / 24.04 LTS
# Usage: sudo ./deploy/setup-ec2.sh
# ==============================================================================

set -e  # Exit on error

if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run as root or with sudo:"
    echo "sudo ./deploy/setup-ec2.sh"
    exit 1
fi

CURRENT_USER=${SUDO_USER:-$USER}
DEPLOY_BASE="/var/www/wvismis"

echo "======================================================"
echo "🚀 Starting Initial EC2 Provisioning for WinVinaya MIS"
echo "Target User: $CURRENT_USER"
echo "Deploy Base: $DEPLOY_BASE"
echo "======================================================"

# 1. Update system packages
echo "📦 1/8 Updating apt repositories and packages..."
apt-get update && apt-get upgrade -y
apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    libpq-dev \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    jq \
    ufw \
    fail2ban \
    htop \
    unzip

# 2. Configure 4GB Swap Space (Critical for EC2 build & memory stability)
echo "💾 2/8 Setting up 4GB swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    echo "✅ 4GB swapfile enabled successfully."
else
    echo "ℹ️  Swapfile already exists. Skipping."
fi

# 3. Install Python 3.11 & virtualenv
echo "🐍 3/8 Installing Python 3.11 and development headers..."
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3.11-distutils \
    python3-pip

# 4. Install Node.js 20.x LTS & PM2
echo "🟢 4/8 Installing Node.js 20.x LTS and PM2..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi
echo "Node version: $(node -v)"
echo "NPM version:  $(npm -v)"

npm install -g pm2
pm2 startup systemd -u "$CURRENT_USER" --hp "/home/$CURRENT_USER" || true

# 5. Install & Configure PostgreSQL 16
echo "🐘 5/8 Installing PostgreSQL 16..."
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt-get update
apt-get install -y postgresql-16 postgresql-contrib-16

systemctl enable postgresql
systemctl start postgresql

echo "Configuring PostgreSQL databases (wvismis_dev and wvismis_prod)..."
sudo -u postgres psql << EOF
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'wvismis_user') THEN
      CREATE ROLE wvismis_user WITH LOGIN PASSWORD 'WinVinayaDb#2026';
   END IF;
END
\$\$;

ALTER ROLE wvismis_user CREATEDB;

SELECT 'CREATE DATABASE wvismis_dev OWNER wvismis_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wvismis_dev')\gexec

SELECT 'CREATE DATABASE wvismis_prod OWNER wvismis_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wvismis_prod')\gexec

GRANT ALL PRIVILEGES ON DATABASE wvismis_dev TO wvismis_user;
GRANT ALL PRIVILEGES ON DATABASE wvismis_prod TO wvismis_user;
EOF

# 6. Install Nginx and Certbot for SSL
echo "🌐 6/8 Installing Nginx web server and Certbot..."
apt-get install -y nginx certbot python3-certbot-nginx
systemctl enable nginx
systemctl start nginx

# 7. Create Project Directories & Permissions
echo "📁 7/8 Creating deployment directory structure..."
mkdir -p \
    $DEPLOY_BASE/backend \
    $DEPLOY_BASE/frontend/dist-dev \
    $DEPLOY_BASE/frontend/dist-prod \
    $DEPLOY_BASE/backups/db \
    $DEPLOY_BASE/logs

chown -R $CURRENT_USER:$CURRENT_USER $DEPLOY_BASE
chmod -R 755 $DEPLOY_BASE

# 8. Configure Firewall (UFW)
echo "🛡️ 8/8 Configuring UFW Firewall..."
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable || true

echo "======================================================"
echo "🎉 EC2 Server Initialization Complete!"
echo "Next Steps:"
echo "1. Clone or copy wvismis repository into $DEPLOY_BASE"
echo "2. Create backend/.env.dev and backend/.env.prod"
echo "3. Copy nginx configurations to /etc/nginx/sites-available/"
echo "4. Run ./deploy/deploy-all.sh dev or prod"
echo "======================================================"
