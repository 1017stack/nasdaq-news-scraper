# 📈 NASDAQ News Scraper

AI-powered news aggregation and sentiment analysis for retail day traders. Filters noise, highlights what matters.

## ✨ Features

- **Smart Impact Classification**: 🔴 High / 🟡 Medium / 🟢 Low impact news
- **AI Sentiment Analysis**: Groq API for intelligent sentiment scoring (-100 to +100)
- **Real-time Dashboard**: Live ticker list with sentiment indicators
- **Sentiment Trends**: 7-day sentiment charts per ticker
- **High Impact Alerts**: Breaking news that actually moves markets
- **Mobile Responsive**: Trade from anywhere

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│   (HTML/JS Dashboard - Dark Mode, Real-time Updates)        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│   Nginx (Reverse Proxy + Static File Serving)               │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                  │
┌───────▼────────┐              ┌──────────▼──────────┐
│   FastAPI      │              │   Python Scraper    │
│   Backend      │              │   (15-min schedule) │
│                │              │                     │
│  • /api/news   │              │  • RSS scraping     │
│  • /api/sent   │              │  • AI sentiment     │
│  • /api/dash   │              │  • Impact classify  │
└───────┬────────┘              └──────────┬──────────┘
        │                                  │
        └──────────────┬───────────────────┘
                       │
              ┌────────▼────────┐
              │   PostgreSQL    │
              │   + TimescaleDB │
              │                 │
              │  • news_items   │
              │  • sentiment    │
              │  • trends       │
              └─────────────────┘
```

## 🚀 Quick Start

### 1. Get a Free Groq API Key
```
1. Go to https://console.groq.com
2. Sign up (no credit card needed)
3. Create an API key
4. Free tier: 1M tokens/day (plenty for this!)
```

### 2. Clone & Configure
```bash
git clone <your-repo>
cd nasdaq-news-scraper
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Run with Docker
```bash
# Build and start everything
docker-compose up --build

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f scraper
```

### 4. Access the App
```
Frontend: http://localhost
API:      http://localhost/api/
```

## 📊 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/tickers` | List all tracked tickers |
| `GET /api/news/{ticker}?impact=high&hours=24` | Get news with filters |
| `GET /api/sentiment/{ticker}?days=7` | Sentiment trend over time |
| `GET /api/dashboard` | Dashboard summary stats |
| `GET /api/high-impact?limit=10` | Latest high-impact news |

## 📡 Data Sources

- **Yahoo Finance RSS** - News aggregation
- **SEC EDGAR RSS** - 8-K filings (coming soon)
- **Benzinga** - Retail trader focused (coming soon)
- **Reddit** - r/wallstreetbets sentiment (coming soon)

## 🎯 Default Tickers

**ETFs:** QQQ, TQQQ, SQQQ, SOXX

**Mega-Caps:** AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA

**Retail Favorites:** AMD, PLTR, COIN, RIVN, LCID, RKLB, INTC

## 💰 Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| Groq API | **FREE** | 1M tokens/day |
| VPS (Railway/Vultr) | ~$5-10/mo | Or free tier |
| PostgreSQL | Included | Docker container |
| **Total** | **$0-10/mo** | For personal use |

## 🔧 Development

### Run Backend Locally
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Run Scraper Locally
```bash
cd scrapers
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python news_scraper.py  # One-time run
python scheduler.py     # Scheduled mode
```

### Run Frontend Locally
```bash
# Just open in browser
open frontend/index.html

# Or use Python server
cd frontend
python -m http.server 8080
```

## 🚢 Deployment Options

### Railway (Recommended - Easiest)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and create project
railway login
railway init

# Deploy
railway up
```

### Render
1. Connect GitHub repo
2. Use "Docker" environment
3. Set environment variables
4. Deploy

### VPS (DigitalOcean/Linode/Vultr)
```bash
# SSH into server
git clone <repo>
cd nasdaq-news-scraper
sudo docker-compose up -d

# Add cron to auto-update
cd /path/to/repo && git pull && docker-compose up -d --build
```

## 🔮 Roadmap

- [ ] SEC EDGAR 8-K filing scraper
- [ ] Options flow integration
- [ ] Email/Push notifications
- [ ] Price correlation analysis
- [ ] Custom watchlists
- [ ] Historical data export

## 📄 License

MIT - Personal use only. Don't scrape paid content.

## ⚠️ Disclaimer

This is for educational purposes. Not financial advice. Always verify sources.
