#!/bin/bash

# NASDAQ News Scraper - Deployment Script
# Supports: Railway, Render, VPS

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║   NASDAQ News Scraper - Deployment Script          ║"
    echo "║   v2.0 - Enhanced with AI + Price Correlation      ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

deploy_railway() {
    echo -e "${YELLOW}🚀 Deploying to Railway...${NC}"

    # Check if railway CLI is available
    if ! command -v railway &> /dev/null; then
        echo "Installing Railway CLI..."
        curl -fsSL https://railway.app/install.sh | sh
        source "$HOME/.railway/env"
    fi

    # Check login
    echo "Checking Railway login..."
    railway whoami || {
        echo -e "${YELLOW}Please login to Railway:${NC}"
        railway login
    }

    # Create project or use existing
    echo "Initializing Railway project..."
    railway init

    # Add PostgreSQL
    echo "Adding PostgreSQL database..."
    railway add --database postgres

    # Set environment variables
    echo "Setting environment variables..."
    railway variables set GROQ_API_KEY="${GROQ_API_KEY}"

    if [ -n "$SENDGRID_API_KEY" ]; then
        railway variables set SENDGRID_API_KEY="$SENDGRID_API_KEY"
        railway variables set NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-alerts@nasdaq-news.com}"
        [ -n "$NOTIFICATION_EMAIL_RECIPIENTS" ] && railway variables set NOTIFICATION_EMAIL_RECIPIENTS="$NOTIFICATION_EMAIL_RECIPIENTS"
    fi

    if [ -n "$TWILIO_ACCOUNT_SID" ]; then
        railway variables set TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID"
        railway variables set TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN"
        railway variables set TWILIO_PHONE_NUMBER="$TWILIO_PHONE_NUMBER"
        [ -n "$NOTIFICATION_SMS_RECIPIENTS" ] && railway variables set NOTIFICATION_SMS_RECIPIENTS="$NOTIFICATION_SMS_RECIPIENTS"
    fi

    # Deploy
    echo "Deploying..."
    railway up

    # Get domain
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    railway domain
}

deploy_render() {
    echo -e "${YELLOW}🚀 Deploying to Render...${NC}"

    # Check if render CLI is available
    if ! command -v render &> /dev/null; then
        echo "Installing Render CLI..."
        curl -fsSL https://raw.githubusercontent.com/render-oss/render-cli/main/install.sh | bash
    fi

    echo -e "${YELLOW}Note: Render deployment requires manual setup via dashboard${NC}"
    echo "1. Go to https://dashboard.render.com"
    echo "2. Create a new Blueprint from this repo"
    echo "3. Set environment variables in dashboard"
    echo ""
    echo "Or use: render blueprint apply"
}

deploy_vps() {
    echo -e "${YELLOW}🚀 Deploying to VPS...${NC}"

    read -p "Enter VPS IP address: " VPS_IP
    read -p "Enter SSH user (default: root): " SSH_USER
    SSH_USER=${SSH_USER:-root}

    echo "Deploying to $SSH_USER@$VPS_IP..."

    # Create remote deploy script
    cat > /tmp/deploy-remote.sh << 'REMOTEEOF'
#!/bin/bash
set -e

# Clone or pull
cd /opt || mkdir -p /opt && cd /opt
if [ -d "nasdaq-news-scraper" ]; then
    cd nasdaq-news-scraper
    git pull
else
    git clone https://github.com/YOUR_USERNAME/nasdaq-news-scraper.git
    cd nasdaq-news-scraper
fi

# Install Docker if needed
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker $USER
fi

# Start services
docker-compose down
docker-compose up -d --build

echo "Deployment complete!"
echo "Frontend: http://$(curl -s ifconfig.me)"
REMOTEEOF

    # Copy and execute
    scp /tmp/deploy-remote.sh "$SSH_USER@$VPS_IP:/tmp/"
    ssh "$SSH_USER@$VPS_IP" "bash /tmp/deploy-remote.sh"

    echo -e "${GREEN}✅ VPS deployment complete!${NC}"
}

local_docker() {
    echo -e "${YELLOW}🐳 Starting local Docker deployment...${NC}"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker not found. Please install Docker first.${NC}"
        exit 1
    fi

    # Build and start
    docker-compose up --build -d

    echo -e "${GREEN}✅ Local deployment complete!${NC}"
    echo "Frontend: http://localhost"
    echo "API: http://localhost:8000"
    echo ""
    echo "View logs: docker-compose logs -f"
}

# Main menu
print_banner

echo "Select deployment target:"
echo "1) Railway (Recommended - Free tier available)"
echo "2) Render (Free tier available)"
echo "3) VPS (DigitalOcean, Hetzner, etc.)"
echo "4) Local Docker"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        deploy_railway
        ;;
    2)
        deploy_render
        ;;
    3)
        deploy_vps
        ;;
    4)
        local_docker
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
