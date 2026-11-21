# CI/CD Automation Guide for WinVinaya MIS (WVISMIS)

WVISMIS uses **GitHub Actions** with two completely separate CI/CD pipelines:

| Environment | Target Domain | Trigger Branch | Workflow File | Port / Directory |
| :--- | :--- | :--- | :--- | :--- |
| **Development** | `https://dev-mis.winvinaya.com` | `dev` | `.github/workflows/dev-pipeline.yml` | Port `8000` / `dist-dev` |
| **Production** | `https://mis.winvinaya.com` | `main` | `.github/workflows/prod-pipeline.yml` | Port `8002` / `dist-prod` |

---

## 1. Required GitHub Repository Secrets

To allow GitHub Actions to securely connect to your AWS EC2 instance and trigger deployments, configure the following secrets in GitHub:

1. Open your repository on GitHub: `https://github.com/winvinayainfosystemsindia/wvismis`
2. Go to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Under **Repository secrets**, click **New repository secret** and add:

| Secret Name | Value | Description |
| :--- | :--- | :--- |
| `EC2_HOST` | `13.204.6.139` *(or your EC2 Elastic IP)* | The Public IPv4 address of the EC2 instance. |
| `EC2_USER` | `ubuntu` | The SSH username for the Ubuntu instance. |
| `EC2_SSH_KEY` | Content of your `.pem` key file | Paste the entire private key including `-----BEGIN ...-----` and `-----END ...-----`. |
| `EC2_PORT` | `22` *(optional)* | SSH port (defaults to 22 if omitted). |

> **Security Note:** Never commit `.pem` files to Git. The `.gitignore` in this project automatically excludes `.pem` files from being tracked.

---

## 2. Pipeline Architecture & Stages

Each pipeline executes two distinct stages:

```
[ Git Push to dev / main ]
           │
           ▼
┌────────────────────────────────────────┐
│ Stage 1: Build & Validate (GitHub Run) │
│  - Python 3.11 requirements & syntax   │
│  - Node.js 20 npm ci & build integrity │
└──────────────────┬─────────────────────┘
                   │  (Only if tests pass)
                   ▼
┌────────────────────────────────────────┐
│ Stage 2: EC2 Deployment via SSH        │
│  - Pulls latest branch (dev / main)    │
│  - Automated DB Backup (backup-db.sh)  │
│  - Alembic Migrations (backend-deploy) │
│  - Superuser Provisioning (scripts)    │
│  - Zero-downtime PM2 reload            │
│  - Production Frontend Build & Publish │
│  - Automated Health Check Verification │
└────────────────────────────────────────┘
```

---

## 3. How to Deploy

### Automatic Deployments
- **Deploy to Development**: Push or merge your code to the `dev` branch:
  ```bash
  git checkout dev
  git add .
  git commit -m "feat: new feature"
  git push origin dev
  ```
  GitHub Actions will automatically run `dev-pipeline.yml` and deploy to `https://dev-mis.winvinaya.com`.

- **Deploy to Production**: Merge `dev` into `main` and push:
  ```bash
  git checkout main
  git merge dev
  git push origin main
  ```
  GitHub Actions will automatically run `prod-pipeline.yml` and deploy to `https://mis.winvinaya.com`.

### Manual Trigger (One-Click)
1. Go to **Actions** in your GitHub repository.
2. In the left sidebar, click **Development CI/CD Pipeline** or **Production CI/CD Pipeline**.
3. Click **Run workflow** $\rightarrow$ select branch $\rightarrow$ click **Run workflow**.

---

## 4. Troubleshooting Deployments

If a deployment fails:
1. Open the failed run in GitHub Actions to view the exact step and console output.
2. In case of deployment rollback on EC2, you can manually rollback to the previous state at any time:
   ```bash
   cd /var/www/wvismis
   ./deploy/rollback.sh dev    # For dev
   ./deploy/rollback.sh prod   # For prod
   ```
