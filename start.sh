#!/bin/bash

# NASDAQ News Scraper - Quick Start Script
# Usage: ./start.sh [command]
# Commands: local, docker, test, clean

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════╗"
    echo "║      NASDAQ News Scraper v1.0           ║"
    echo "║   AI-Powered Market Intelligence        ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  local    - Run locally with Python virtualenv"
    echo "  docker   - Run with Docker Compose"
    echo "  test     - Run scraper test on single ticker"
    echo "  clean    - Clean up containers and volumes"
    echo "  setup    - First-time setup"
    echo ""
}

setup_env() {
    echo -e "${YELLOW}🔧 First-time setup...${NC}"

    if [ ! -f .env ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env and add your GROQ_API_KEY${NC}"
        echo "   Get a free key at: https://console.groq.com"
        exit 0
    fi

    # Create virtual environments
    if [ ! -d backend/venv ]; then
        echo "Creating backend virtualenv..."
        cd backend && python3 -m venv venv && cd ..
        backend/venv/bin/pip install -r backend/requirements.txt
        echo -e "${GREEN}✓ Backend venv created${NC}"
    fi

    if [ ! -d scrapers/venv ]; then
        echo "Creating scraper virtualenv..."
        cd scrapers && python3 -m venv venv && cd ..
        scrapers/venv/bin/pip install -r scrapers/requirements.txt
        echo -e "${GREEN}✓ Scraper venv created${NC}"
    fi

    echo -e "${GREEN}✓ Setup complete!${NC}"
}

run_local() {
    print_banner
    echo -e "${YELLOW}🚀 Starting local development mode...${NC}"

    # Check .env
    if [ ! -f .env ]; then
        setup_env
    fi

    # Load env vars
    export $(grep -v '^#' .env | xargs)

    # Start PostgreSQL with Docker
    echo "📦 Starting PostgreSQL..."
    docker run -d \
        --name nasdaq-postgres \
        -e POSTGRES_USER=nasdaq_user \
        -e POSTGRES_PASSWORD=nasdaq_pass \
        -e POSTGRES_DB=nasdaq_news \
        -p 5432:5432 \
        -v nasdaq_postgres_data:/var/lib/postgresql/data \
        postgres:16-alpine 2>/dev/null || echo "PostgreSQL already running"

    # Wait for PostgreSQL
    echo "⏳ Waiting for PostgreSQL..."
    sleep 3

    # Start backend
    echo "🌐 Starting FastAPI backend on http://localhost:8000"
    cd backend
    venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    cd ..

    # Start frontend server
    echo "🎨 Starting frontend on http://localhost:8080"
    cd frontend
    python3 -m http.server 8080 &
    FRONTEND_PID=$!
    cd ..

    echo ""
    echo -e "${GREEN}✓ Services started!${NC}"
    echo "  Frontend: http://localhost:8080"
    echo "  API:      http://localhost:8000"
    echo "  Docs:     http://localhost:8000/docs"
    echo ""
    echo "Press Ctrl+C to stop all services"

    # Wait for interrupt
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker stop nasdaq-postgres 2>/dev/null; exit" INT
    wait
}

run_docker() {
    print_banner
    echo -e "${YELLOW}🐳 Starting with Docker Compose...${NC}"

    # Check .env
    if [ ! -f .env ]; then
        setup_env
        exit 0
    fi

    # Build and start
    docker-compose up --build -d

    echo ""
    echo -e "${GREEN}✓ Services started!${NC}"
    echo "  Frontend: http://localhost"
    echo "  API:      http://localhost/api"
    echo "  Docs:     http://localhost/api/docs"
    echo ""
    echo "View logs: docker-compose logs -f"
    echo "Stop:      docker-compose down"
}

run_test() {
    print_banner
    echo -e "${YELLOW}🧪 Running scraper test...${NC}"

    if [ ! -f .env ]; then
        echo -e "${RED}Error: .env file not found. Run: ./start.sh setup${NC}"
        exit 1
    fi

    export $(grep -v '^#' .env | xargs)

    # Ensure PostgreSQL is running
    docker run -d \
        --name nasdaq-postgres \
        -e POSTGRES_USER=nasdaq_user \
        -e POSTGRES_PASSWORD=nasdaq_pass \
        -e POSTGRES_DB=nasdaq_news \
        -p 5432:5432 \
        postgres:16-alpine 2>/dev/null || true

    sleep 3

    # Run test
    cd scrapers
    venv/bin/python -c "
import asyncio
from news_scraper import NewsScraper

async def test():
    print('Initializing scraper...')
    scraper = NewsScraper()
    await scraper.init()

    print('\nTesting with NVDA...')
    result = await scraper.scrape_ticker('NVDA')
    print(f\"Result: {result}\")

    await scraper.close()
    print('\n✓ Test complete!')

asyncio.run(test())
"
}

cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up...${NC}"

    # Stop containers
    docker-compose down -v 2>/dev/null || true
    docker stop nasdaq-postgres 2>/dev/null || true
    docker rm nasdaq-postgres 2>/dev/null || true
    docker volume rm nasdaq_postgres_data 2>/dev/null || true

    # Remove pycache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Main
COMMAND=${1:-help}

case $COMMAND in
    setup)
        setup_env
        ;;
    local)
        run_local
        ;;
    docker)
        run_docker
        ;;
    test)
        run_test
        ;;
    clean|cleanup)
        cleanup
        ;;
    *)
        print_banner
        print_help
        ;;
esac
