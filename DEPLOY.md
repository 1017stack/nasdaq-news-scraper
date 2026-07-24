# 🚀 Deployment Guide

## Quick Deploy to Railway (Recommended)

Railway offers a generous free tier and zero-config deployment.

### 1. Prerequisites
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login
```

### 2. Deploy
```bash
cd nasdaq-news-scraper

# Create project
railway init

# Add PostgreSQL
railway add --database postgres

# Set environment variables
railway variables set GROQ_API_KEY="your_key_here"

# Deploy
railway up
```

### 3. Get Public URL
```bash
railway domain
# Copy the URL and open in browser
```

---

## Deploy to Render

### 1. Create render.yaml
```yaml
services:
  - type: web
    name: nasdaq-frontend
    runtime: static
    buildCommand: echo "Static files ready"
    staticPublishPath: ./frontend
    routes:
      - type: rewrite
        source: /api/*
        destination: https://nasdaq-backend.onrender.com/api/

  - type: web
    name: nasdaq-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nasdaq-db
          property: connectionString
      - key: GROQ_API_KEY
        sync: false

  - type: worker
    name: nasdaq-scraper
    runtime: docker
    dockerfilePath: ./scrapers/Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nasdaq-db
          property: connectionString
      - key: GROQ_API_KEY
        sync: false

databases:
  - name: nasdaq-db
    databaseName: nasdaq_news
    user: nasdaq_user
```

### 2. Deploy
1. Push to GitHub
2. Connect Render to your repo
3. Create Blueprint from render.yaml
4. Add GROQ_API_KEY in dashboard

---

## Deploy to VPS (Hetzner/DigitalOcean)

### 1. Provision Server
```bash
# Hetzner (cheapest option)
# CX22 instance: 2 vCPU, 4GB RAM, 40GB SSD = ~€4.51/mo
```

### 2. SSH Setup
```bash
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Install Docker Compose
apt install docker-compose-plugin -y
```

### 3. Deploy
```bash
# Clone repo
git clone https://github.com/yourusername/nasdaq-news-scraper.git
cd nasdaq-news-scraper

# Create .env file
cat > .env << EOL
DATABASE_URL=postgresql://nasdaq_user:nasdaq_pass@postgres:5432/nasdaq_news
GROQ_API_KEY=your_groq_api_key_here
EOL

# Start services
docker-compose up -d

# Verify
docker-compose ps
docker-compose logs -f
```

### 4. Setup Auto-SSL with Let's Encrypt
```bash
# Install nginx and certbot
apt install nginx certbot python3-certbot-nginx -y

# Create nginx config
cat > /etc/nginx/sites-available/nasdaq << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}
EOF

ln -s /etc/nginx/sites-available/nasdaq /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Get SSL certificate
certbot --nginx -d your-domain.com
```

### 5. Setup Auto-Updates
```bash
# Create update script
cat > /opt/update-nasdaq.sh << 'EOF'
#!/bin/bash
cd /root/nasdaq-news-scraper
git pull
docker-compose up -d --build
docker system prune -f
EOF

chmod +x /opt/update-nasdaq.sh

# Add cron job (update daily at 3am)
echo "0 3 * * * /opt/update-nasdaq.sh >> /var/log/nasdaq-update.log 2>&1" | crontab -
```

---

## Free Hosting Alternatives

### Fly.io (Free Tier: $5 credit/month)
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Launch
flyctl launch

# Scale to free tier
flyctl scale shared-cpu-1x --memory 256
```

### Oracle Cloud Free Tier (Always Free)
- 2 AMD-based Compute VMs
- 4 Arm-based Ampere A1 cores
- 24GB RAM total
- Perfect for this project

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `GROQ_API_KEY` | No | - | Free LLM API for sentiment |
| `SCRAPE_INTERVAL` | No | 15 | Minutes between scrapes |
| `MAX_ARTICLES` | No | 10 | Articles per ticker per run |

---

## Troubleshooting

### Scraper not saving articles
```bash
# Check logs
docker-compose logs scraper

# Verify database connection
docker-compose exec postgres psql -U nasdaq_user -d nasdaq_news -c "SELECT COUNT(*) FROM news_items;"
```

### Frontend can't connect to API
```bash
# Check if backend is running
docker-compose ps backend

# Test API directly
curl http://localhost:8000/api/tickers
```

### Database errors
```bash
# Reset database (WARNING: Deletes all data!)
docker-compose down -v
docker-compose up -d
```

### Rate limiting
If you hit rate limits:
- Add `asyncio.sleep(2)` between requests
- Rotate user agents
- Use proxy rotation (for production)

---

## Monitoring

### Setup Health Checks
Add to docker-compose.yml:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Uptime Monitoring (Free)
- UptimeRobot: https://uptimerobot.com (50 monitors free)
- Healthchecks.io: https://healthchecks.io (20 checks free)

---

## Backup Strategy

```bash
# Backup script
cat > /opt/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T postgres pg_dump -U nasdaq_user nasdaq_news > /backups/nasdaq_$DATE.sql
find /backups -name "nasdaq_*.sql" -mtime +7 -delete
EOF

# Daily backup at 2am
echo "0 2 * * * /opt/backup.sh" | crontab -
```
