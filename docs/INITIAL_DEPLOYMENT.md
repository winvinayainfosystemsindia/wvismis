# Initial Deployment Guide for WinVinaya MIS (WVISMIS) on AWS EC2

This comprehensive guide covers the end-to-end process of provisioning, configuring, deploying, and maintaining **WinVinaya MIS** (Backend, Frontend, and PostgreSQL Database) across **Development** and **Production** environments on an **AWS EC2** instance.

---

## 📑 Table of Contents

1. [EC2 Instance Requirements & Security Groups](#1-ec2-instance-requirements--security-groups)
2. [SSH Key Permissions & Connecting to EC2](#2-ssh-key-permissions--connecting-to-ec2)
3. [Server Initial Setup (Automated & Manual)](#3-server-initial-setup)
4. [PostgreSQL Database Setup](#4-postgresql-database-setup)
5. [Cloning the Repository](#5-cloning-the-repository)
6. [Environment Configuration (.env)](#6-environment-configuration)
7. [Backend Setup & Alembic Migrations](#7-backend-setup--alembic-migrations)
8. [Frontend Build & Setup](#8-frontend-build--setup)
9. [Nginx Configuration](#9-nginx-configuration)
10. [SSL Setup via Let's Encrypt (Certbot)](#10-ssl-setup-via-lets-encrypt-certbot)
11. [PM2 Process Management & Persistence](#11-pm2-process-management--persistence)
12. [Verification, Health Checks & Monitoring](#12-verification-health-checks--monitoring)
13. [Database Backup & Restore Strategy](#13-database-backup--restore-strategy)
14. [Rollback & Zero-Downtime Updates](#14-rollback--zero-downtime-updates)

---

## 1. EC2 Instance Requirements & Security Groups

### Recommended Hardware Specifications
- **Operating System**: Ubuntu 22.04 LTS or 24.04 LTS (64-bit x86)
- **Instance Type**: 
  - `t3.medium` (Recommended: 2 vCPU, 4GB RAM)
  - `t3.small` (Minimum: 2 vCPU, 2GB RAM — requires 4GB swap space enabled)
- **Storage**: 30GB to 50GB gp3 SSD
- **Networking**: Allocate and associate an **Elastic IP** to your EC2 instance so your public IP address remains static.

### Inbound Security Group Rules

| Type | Protocol | Port Range | Source | Description |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | Your IP / Bastion | Secure CLI access |
| **HTTP** | TCP | `80` | `0.0.0.0/0` | Let's Encrypt verification & HTTP to HTTPS redirect |
| **HTTPS** | TCP | `443` | `0.0.0.0/0` | Secure SSL web traffic |

### DNS Configuration (Domain Registrar / AWS Route53)

Configure the following DNS records pointing to your EC2 **Elastic IP**:

| Record Type | Hostname / Subdomain | Target Value |
| :--- | :--- | :--- |
| **A Record** | `dev-mis.winvinaya.com` | `YOUR_EC2_ELASTIC_IP` |
| **A Record** | `mis.winvinaya.com` | `YOUR_EC2_ELASTIC_IP` |
| **CNAME** | `www.mis.winvinaya.com` | `mis.winvinaya.com` |

---

## 2. SSH Key Permissions & Connecting to EC2

### Windows (PowerShell)
If using Windows, fix file permissions on your `.pem` key before connecting:
```powershell
# Reset and restrict access to current user only
icacls.exe winvinaya-ec2.pem /reset
icacls.exe winvinaya-ec2.pem /inheritance:r
icacls.exe winvinaya-ec2.pem /grant:r "$($env:USERNAME):(R)"

# Connect to EC2
ssh -i winvinaya-ec2.pem ubuntu@YOUR_EC2_ELASTIC_IP
```

### Linux / macOS
```bash
chmod 400 winvinaya-ec2.pem
ssh -i winvinaya-ec2.pem ubuntu@YOUR_EC2_ELASTIC_IP
```

---

## 3. Server Initial Setup

You can provision the entire server automatically using the included setup script or manually.

### Option A: Automated Provisioning (Recommended)
```bash
# Clone or copy wvismis to /var/www/wvismis
sudo mkdir -p /var/www/wvismis
sudo chown -R $USER:$USER /var/www/wvismis

# Run automated setup script
chmod +x /var/www/wvismis/deploy/*.sh
sudo /var/www/wvismis/deploy/setup-ec2.sh
```

### Option B: Manual Setup
```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential libpq-dev curl wget git jq ufw fail2ban htop unzip

# 2. Configure 4GB Swap Space (Crucial for Node.js / Vite build memory)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# 3. Install Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3.11-distutils python3-pip

# 4. Install Node.js 20 LTS & PM2
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2
pm2 startup systemd -u ubuntu --hp /home/ubuntu

# 5. Install PostgreSQL 16
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 6. Install Nginx and Certbot
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# 7. Configure Firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

---

## 4. PostgreSQL Database Setup

Log into PostgreSQL and create the user and databases for Development and Production:

```bash
sudo -u postgres psql
```

Run the following SQL commands:

```sql
-- 1. Create dedicated application user
CREATE USER wvismis_user WITH LOGIN PASSWORD 'WinVinayaDb#2026';
ALTER ROLE wvismis_user CREATEDB;

-- 2. Create Development and Production databases
CREATE DATABASE wvismis_dev OWNER wvismis_user;
CREATE DATABASE wvismis_prod OWNER wvismis_user;

-- 3. Grant privileges
GRANT ALL PRIVILEGES ON DATABASE wvismis_dev TO wvismis_user;
GRANT ALL PRIVILEGES ON DATABASE wvismis_prod TO wvismis_user;

-- 4. Set schema permissions
\c wvismis_dev
GRANT ALL ON SCHEMA public TO wvismis_user;
ALTER DEFAULT PRIVILEGES FOR USER wvismis_user GRANT ALL ON TABLES TO wvismis_user;
ALTER DEFAULT PRIVILEGES FOR USER wvismis_user GRANT ALL ON SEQUENCES TO wvismis_user;

\c wvismis_prod
GRANT ALL ON SCHEMA public TO wvismis_user;
ALTER DEFAULT PRIVILEGES FOR USER wvismis_user GRANT ALL ON TABLES TO wvismis_user;
ALTER DEFAULT PRIVILEGES FOR USER wvismis_user GRANT ALL ON SEQUENCES TO wvismis_user;

-- Exit psql
\q
```

---

## 5. Cloning the Repository

```bash
sudo mkdir -p /var/www/wvismis
sudo chown -R ubuntu:ubuntu /var/www/wvismis
cd /var/www/wvismis

# Clone via HTTPS or SSH
git clone <YOUR_GIT_REPO_URL> .
chmod +x deploy/*.sh
```

---

## 6. Environment Configuration

### 6.1 Backend Configuration

```bash
cd /var/www/wvismis/backend

# Development Configuration
cp .env.dev.example .env.dev
nano .env.dev
```

Key values for `backend/.env.dev`:
```ini
APP_NAME="WVISMIS - WinVinaya MIS (Development)"
ENVIRONMENT=development
PORT=8000
HOST=127.0.0.1

POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=wvismis_user
POSTGRES_PASSWORD=WinVinayaDb#2026
POSTGRES_DB=wvismis_dev

SECRET_KEY=generate_with_openssl_rand_hex_32
BACKEND_CORS_ORIGINS=https://dev-mis.winvinaya.com,http://localhost:5173

# Email Notifications (WinVinaya SMTP)
SMTP_TLS=True
SMTP_PORT=587
SMTP_HOST=s.mail25.info
SMTP_USER=no-reply@winvinaya.com
SMTP_PASSWORD=Admin##2025@
EMAILS_FROM_EMAIL=no-reply@winvinaya.com
EMAILS_FROM_NAME="WinVinaya MIS"
```

```bash
# Production Configuration
cp .env.prod.example .env.prod
nano .env.prod
```

Key values for `backend/.env.prod`:
```ini
APP_NAME="WVISMIS - WinVinaya MIS"
ENVIRONMENT=production
PORT=8002
HOST=127.0.0.1
DEBUG=False

POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=wvismis_user
POSTGRES_PASSWORD=WinVinayaDb#2026
POSTGRES_DB=wvismis_prod

SECRET_KEY=generate_with_openssl_rand_hex_32
BACKEND_CORS_ORIGINS=https://mis.winvinaya.com,https://www.mis.winvinaya.com

# Email Notifications (WinVinaya SMTP)
SMTP_TLS=True
SMTP_PORT=587
SMTP_HOST=s.mail25.info
SMTP_USER=no-reply@winvinaya.com
SMTP_PASSWORD=Admin##2025@
EMAILS_FROM_EMAIL=no-reply@winvinaya.com
EMAILS_FROM_NAME="WinVinaya MIS"
```

### 6.2 Frontend Configuration

```bash
cd /var/www/wvismis/frontend

# Development
cat << 'EOF' > .env.dev
VITE_API_URL=https://dev-mis.winvinaya.com
VITE_ENVIRONMENT=development
EOF

# Production
cat << 'EOF' > .env.prod
VITE_API_URL=https://mis.winvinaya.com
VITE_ENVIRONMENT=production
EOF
```

---

## 7. Backend Setup & Alembic Migrations

You can set up each environment using `./deploy/backend-deploy.sh {dev|prod}` or manually:

### Setup Development Backend
```bash
cd /var/www/wvismis
./deploy/backend-deploy.sh dev
```

### Setup Production Backend
```bash
cd /var/www/wvismis
./deploy/backend-deploy.sh prod
```

*What this does:*
1. Creates dedicated virtual environment (`venv-dev` / `venv-prod`).
2. Installs all packages from `requirements.txt`.
3. Runs database migrations: `alembic upgrade head`.
4. Starts the FastAPI server via PM2 (`wvismis-backend-dev` on port 8000, `wvismis-backend-prod` on port 8002).

---

## 8. Frontend Build & Setup

### Deploy Development Frontend
```bash
cd /var/www/wvismis
./deploy/frontend-deploy.sh dev
```
*Builds React bundle using `.env.dev` and deploys to `/var/www/wvismis/frontend/dist-dev`.*

### Deploy Production Frontend
```bash
cd /var/www/wvismis
./deploy/frontend-deploy.sh prod
```
*Builds React bundle using `.env.prod` and deploys to `/var/www/wvismis/frontend/dist-prod`.*

---

## 9. Nginx Configuration

The repository contains pre-configured Nginx site definitions in the root `nginx/` folder:

1. **Copy configurations to Nginx available sites**:
   ```bash
   sudo cp /var/www/wvismis/nginx/dev.conf /etc/nginx/sites-available/wvismis-dev.conf
   sudo cp /var/www/wvismis/nginx/prod.conf /etc/nginx/sites-available/wvismis-prod.conf
   ```

2. **Enable sites**:
   ```bash
   sudo ln -sf /etc/nginx/sites-available/wvismis-dev.conf /etc/nginx/sites-enabled/
   sudo ln -sf /etc/nginx/sites-available/wvismis-prod.conf /etc/nginx/sites-enabled/
   ```

3. **Remove default Nginx site and test configuration**:
   ```bash
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl reload nginx
   ```

---

## 10. SSL Setup via Let's Encrypt (Certbot)

Once your DNS A-records are pointing to your EC2 instance's Elastic IP, obtain free automated SSL certificates:

```bash
cd /var/www/wvismis

# Obtain SSL for both dev and prod
sudo ./deploy/setup-ssl.sh both
```

Or run Certbot manually:
```bash
sudo certbot --nginx -d dev-mis.winvinaya.com --non-interactive --agree-tos --email admin@winvinaya.com --redirect
sudo certbot --nginx -d mis.winvinaya.com -d www.mis.winvinaya.com --non-interactive --agree-tos --email admin@winvinaya.com --redirect

# Test automatic renewal
sudo certbot renew --dry-run
```

---

## 11. PM2 Process Management & Persistence

PM2 manages background processes, automatic restarts on failure, and server boot restarts.

```bash
# View active processes
pm2 status

# Monitor live CPU & Memory usage
pm2 monit

# Save current PM2 processes to restart upon server reboot
pm2 save

# View logs
pm2 logs wvismis-backend-dev
pm2 logs wvismis-backend-prod
```

---

## 12. Verification, Health Checks & Monitoring

Execute the automated health check script:
```bash
# Development check
./deploy/health-check.sh dev

# Production check
./deploy/health-check.sh prod
```

Manual endpoint verification:
```bash
# 1. Backend internal health checks
curl -i http://localhost:8000/health
curl -i http://localhost:8002/health

# 2. Public domain health checks
curl -i https://dev-mis.winvinaya.com/health
curl -i https://mis.winvinaya.com/health

# 3. Interactive API documentation
# Dev:  https://dev-mis.winvinaya.com/docs
# Prod: https://mis.winvinaya.com/docs
```

---

## 13. Database Backup & Restore Strategy

### Run Manual Backup
```bash
# Backup Development DB
./deploy/backup-db.sh dev

# Backup Production DB
./deploy/backup-db.sh prod
```
*Backups are saved to `/var/www/wvismis/backups/db/` with gzip compression. The script automatically rotates and retains the latest 14 backups.*

### Automate Nightly Backups (Cronjob)
```bash
crontab -e
```
Add:
```cron
# Daily DB Backups: 2:00 AM (Dev), 2:30 AM (Prod)
0 2 * * * /var/www/wvismis/deploy/backup-db.sh dev >> /var/www/wvismis/logs/backup_cron.log 2>&1
30 2 * * * /var/www/wvismis/deploy/backup-db.sh prod >> /var/www/wvismis/logs/backup_cron.log 2>&1
```

### Restore Database
```bash
# Restores from latest backup file automatically
./deploy/restore-db.sh dev

# Or restore a specific backup file
./deploy/restore-db.sh prod /var/www/wvismis/backups/db/wvismis_prod_20261121_023000.sql.gz
```

---

## 14. Rollback & Zero-Downtime Updates

### Routine Updates
When deploying new code changes:
```bash
cd /var/www/wvismis
git pull origin main   # or develop

# One-click automated deployment
./deploy/deploy-all.sh dev   # or prod
```

### Emergency Rollback
If a deployment introduces a critical bug:
```bash
cd /var/www/wvismis
./deploy/rollback.sh dev    # or prod
```
*The rollback script automatically checks out the previous Git commit (`HEAD~1`), restores the pre-deployment database backup, redeploys the backend & frontend, and validates system health.*
