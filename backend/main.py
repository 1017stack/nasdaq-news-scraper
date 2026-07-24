"""
NASDAQ News Scraper - Backend API
FastAPI server for serving scraped news with AI sentiment analysis
Enhanced with price correlation, Reddit sentiment, SEC filings
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import asyncpg
import os
from contextlib import asynccontextmanager

# Database connection pool
DB_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/nasdaq_news")

# Default tickers to track
DEFAULT_TICKERS = [
    "QQQ", "TQQQ", "SQQQ", "SOXX",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "AMD", "PLTR", "COIN", "RIVN", "LCID", "RKLB", "INTC"
]

# Pydantic models
class NewsItem(BaseModel):
    id: int
    ticker: str
    headline: str
    source: str
    url: str
    published_at: datetime
    impact_level: str
    sentiment_score: float
    ai_summary: Optional[str]
    category: Optional[str]
    sec_items: Optional[list]
    price_correlation: Optional[dict]

class SentimentTrend(BaseModel):
    date: datetime
    avg_sentiment: float
    news_count: int

class PriceData(BaseModel):
    timestamp: datetime
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: float
    volume: Optional[int]

class PriceCorrelationResponse(BaseModel):
    ticker: str
    news_time: str
    price_at_news: float
    pre_news_price: float
    post_news_price: float
    change_before_news_pct: float
    change_after_news_pct: float
    total_change_pct: float

class RedditSentiment(BaseModel):
    ticker: str
    mentions_24h: int
    avg_sentiment: float
    sentiment_label: str
    top_posts: List[dict]

class TickerSummary(BaseModel):
    ticker: str
    latest_sentiment: Optional[float]
    sentiment_24h_change: Optional[float]
    high_impact_count_24h: int
    last_updated: Optional[datetime]

class DashboardResponse(BaseModel):
    tickers: List[dict]
    total_high_impact_24h: int
    market_sentiment: Optional[str]
    reddit_trending: List[str]

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await asyncpg.connect(DB_URL)

    # Create tables with new columns
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) NOT NULL,
            headline TEXT NOT NULL,
            source VARCHAR(100) NOT NULL,
            url TEXT NOT NULL,
            published_at TIMESTAMP NOT NULL,
            scraped_at TIMESTAMP DEFAULT NOW(),
            impact_level VARCHAR(10) CHECK (impact_level IN ('high', 'medium', 'low')),
            sentiment_score FLOAT CHECK (sentiment_score BETWEEN -100 AND 100),
            ai_summary TEXT,
            category VARCHAR(50),
            sec_items JSONB,
            price_correlation JSONB,
            raw_content TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_items(ticker);
        CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_news_impact ON news_items(impact_level);
        CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category);

        -- Price data table
        CREATE TABLE IF NOT EXISTS price_data (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open FLOAT,
            high FLOAT,
            low FLOAT,
            close FLOAT,
            volume BIGINT,
            UNIQUE(ticker, timestamp)
        );
        CREATE INDEX IF NOT EXISTS idx_price_ticker_time ON price_data(ticker, timestamp DESC);

        -- Reddit sentiment table
        CREATE TABLE IF NOT EXISTS reddit_sentiment (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) NOT NULL,
            mentions_24h INTEGER DEFAULT 0,
            avg_sentiment FLOAT,
            sentiment_label VARCHAR(20),
            top_posts JSONB,
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(ticker)
        );
        CREATE INDEX IF NOT EXISTS idx_reddit_ticker ON reddit_sentiment(ticker);
    """)

    await conn.close()
    print("✅ Database initialized with enhanced schema")
    yield
    print("👋 Server shutting down")

app = FastAPI(
    title="NASDAQ News Scraper API",
    description="AI-powered news filtering with price correlation and Reddit sentiment",
    version="2.0.0",
    lifespan=lifespan
)

# CORS for frontend
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
origins = [FRONTEND_URL] if FRONTEND_URL != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db():
    """Get database connection"""
    return await asyncpg.connect(DB_URL)

@app.get("/")
async def root():
    return {
        "message": "NASDAQ News Scraper API",
        "version": "2.0.0",
        "features": ["news", "sentiment", "price_correlation", "reddit_sentiment", "sec_filings"],
        "tickers_tracked": len(DEFAULT_TICKERS),
        "tickers": DEFAULT_TICKERS
    }

@app.get("/api/tickers", response_model=List[str])
async def get_tickers():
    """Get all tracked tickers"""
    return DEFAULT_TICKERS

@app.get("/api/news/{ticker}", response_model=List[dict])
async def get_news(
    ticker: str,
    limit: int = 20,
    impact: Optional[str] = None,
    category: Optional[str] = None,
    hours: int = 48
):
    """Get news for a specific ticker with optional filtering"""
    conn = await get_db()
    try:
        cutoff = datetime.now() - timedelta(hours=hours)

        query = """
            SELECT
                id, ticker, headline, source, url, published_at,
                impact_level, sentiment_score, ai_summary, category,
                sec_items, price_correlation
            FROM news_items
            WHERE ticker = $1 AND published_at > $2
        """
        params = [ticker.upper(), cutoff]

        if impact:
            query += f" AND impact_level = ${len(params) + 1}"
            params.append(impact)

        if category:
            query += f" AND category = ${len(params) + 1}"
            params.append(category)

        query += f" ORDER BY published_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        rows = await conn.fetch(query, *params)

        # Convert to dict and parse JSON
        results = []
        for row in rows:
            item = dict(row)
            if item.get('sec_items'):
                item['sec_items'] = item['sec_items']
            if item.get('price_correlation'):
                item['price_correlation'] = item['price_correlation']
            results.append(item)

        return results
    finally:
        await conn.close()

@app.get("/api/sentiment/{ticker}")
async def get_sentiment(ticker: str, days: int = 7):
    """Get sentiment trend for a ticker over time"""
    conn = await get_db()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        rows = await conn.fetch("""
            SELECT
                DATE_TRUNC('day', published_at) as date,
                AVG(sentiment_score) as avg_sentiment,
                COUNT(*) as news_count
            FROM news_items
            WHERE ticker = $1 AND published_at > $2
            GROUP BY DATE_TRUNC('day', published_at)
            ORDER BY date DESC
        """, ticker.upper(), cutoff)

        return {
            "ticker": ticker.upper(),
            "trend": [dict(row) for row in rows]
        }
    finally:
        await conn.close()

@app.get("/api/sentiment/{ticker}/reddit")
async def get_reddit_sentiment(ticker: str):
    """Get Reddit sentiment for a ticker"""
    conn = await get_db()
    try:
        row = await conn.fetchrow("""
            SELECT * FROM reddit_sentiment WHERE ticker = $1
        """, ticker.upper())

        if row:
            return dict(row)
        else:
            return {"ticker": ticker.upper(), "mentions_24h": 0, "avg_sentiment": 0}
    finally:
        await conn.close()

@app.get("/api/price/{ticker}")
async def get_price_data(
    ticker: str,
    period: str = "1d",
    interval: str = "15m"
):
    """Get price data for a ticker"""
    conn = await get_db()
    try:
        # Map period to hours
        period_map = {"1d": 24, "5d": 120, "1mo": 720, "3mo": 2160}
        hours = period_map.get(period, 24)
        cutoff = datetime.now() - timedelta(hours=hours)

        rows = await conn.fetch("""
            SELECT timestamp, open, high, low, close, volume
            FROM price_data
            WHERE ticker = $1 AND timestamp > $2
            ORDER BY timestamp ASC
        """, ticker.upper(), cutoff)

        return {
            "ticker": ticker.upper(),
            "period": period,
            "interval": interval,
            "prices": [dict(row) for row in rows]
        }
    finally:
        await conn.close()

@app.get("/api/correlation/{ticker}")
async def get_price_correlation(
    ticker: str,
    news_id: Optional[int] = None,
    hours: int = 4
):
    """Get price correlation around news events"""
    conn = await get_db()
    try:
        if news_id:
            # Get specific news item correlation
            row = await conn.fetchrow("""
                SELECT price_correlation FROM news_items WHERE id = $1 AND ticker = $2
            """, news_id, ticker.upper())

            if row and row['price_correlation']:
                return row['price_correlation']

        # Otherwise get recent high-impact correlations
        cutoff = datetime.now() - timedelta(hours=hours)
        rows = await conn.fetch("""
            SELECT headline, published_at, price_correlation
            FROM news_items
            WHERE ticker = $1 AND impact_level = 'high'
            AND price_correlation IS NOT NULL
            AND published_at > $2
            ORDER BY published_at DESC
            LIMIT 5
        """, ticker.upper(), cutoff)

        return {
            "ticker": ticker.upper(),
            "correlations": [dict(row) for row in rows]
        }
    finally:
        await conn.close()

@app.get("/api/dashboard")
async def get_dashboard():
    """Get summary dashboard for all tickers"""
    conn = await get_db()
    try:
        cutoff = datetime.now() - timedelta(hours=24)

        # Get ticker summaries
        rows = await conn.fetch("""
            SELECT
                ticker,
                AVG(sentiment_score) as latest_sentiment,
                COUNT(CASE WHEN impact_level = 'high' THEN 1 END) as high_impact_count,
                COUNT(*) as total_news,
                MAX(published_at) as last_updated
            FROM news_items
            WHERE published_at > $1
            GROUP BY ticker
            ORDER BY high_impact_count DESC, total_news DESC
        """, cutoff)

        # Get trending tickers from Reddit
        reddit_rows = await conn.fetch("""
            SELECT ticker, mentions_24h, avg_sentiment
            FROM reddit_sentiment
            WHERE mentions_24h > 10
            ORDER BY mentions_24h DESC
            LIMIT 5
        """)

        # Calculate overall market sentiment
        market_sentiment = await conn.fetchval("""
            SELECT AVG(sentiment_score) FROM news_items
            WHERE published_at > $1 AND impact_level IN ('high', 'medium')
        """, cutoff)

        return {
            "tickers": [dict(row) for row in rows],
            "total_high_impact_24h": sum(r['high_impact_count'] for r in rows),
            "market_sentiment": round(market_sentiment, 1) if market_sentiment else 0,
            "reddit_trending": [r['ticker'] for r in reddit_rows],
            "reddit_details": [dict(row) for row in reddit_rows]
        }
    finally:
        await conn.close()

@app.get("/api/high-impact")
async def get_high_impact_alerts(limit: int = 10):
    """Get latest high-impact news across all tickers"""
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT
                id, ticker, headline, source, url, published_at,
                impact_level, sentiment_score, ai_summary, category,
                sec_items, price_correlation
            FROM news_items
            WHERE impact_level = 'high'
            ORDER BY published_at DESC
            LIMIT $1
        """, limit)

        results = []
        for row in rows:
            item = dict(row)
            if item.get('sec_items'):
                item['sec_items'] = item['sec_items']
            if item.get('price_correlation'):
                item['price_correlation'] = item['price_correlation']
            results.append(item)

        return results
    finally:
        await conn.close()

@app.get("/api/sec-filings/{ticker}")
async def get_sec_filings(ticker: str, limit: int = 10):
    """Get SEC filings for a ticker"""
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT *
            FROM news_items
            WHERE ticker = $1 AND source = 'SEC EDGAR'
            ORDER BY published_at DESC
            LIMIT $2
        """, ticker.upper(), limit)

        return [dict(row) for row in rows]
    finally:
        await conn.close()

@app.get("/api/market-overview")
async def get_market_overview():
    """Get overall market overview with top movers"""
    conn = await get_db()
    try:
        cutoff = datetime.now() - timedelta(hours=6)

        # Most discussed tickers
        hot_tickers = await conn.fetch("""
            SELECT
                ticker,
                COUNT(*) as mention_count,
                AVG(ABS(sentiment_score)) as avg_intensity
            FROM news_items
            WHERE published_at > $1
            GROUP BY ticker
            ORDER BY mention_count DESC
            LIMIT 10
        """, cutoff)

        # Sentiment distribution
        sentiment_dist = await conn.fetch("""
            SELECT
                CASE
                    WHEN sentiment_score > 30 THEN 'bullish'
                    WHEN sentiment_score < -30 THEN 'bearish'
                    ELSE 'neutral'
                END as sentiment,
                COUNT(*) as count
            FROM news_items
            WHERE published_at > $1
            GROUP BY sentiment
        """, cutoff)

        # Recent high impact by category
        category_breakdown = await conn.fetch("""
            SELECT
                category,
                COUNT(*) as count,
                AVG(sentiment_score) as avg_sentiment
            FROM news_items
            WHERE published_at > $1 AND impact_level = 'high'
            GROUP BY category
            ORDER BY count DESC
        """, cutoff)

        return {
            "hot_tickers": [dict(row) for row in hot_tickers],
            "sentiment_distribution": {row['sentiment']: row['count'] for row in sentiment_dist},
            "category_breakdown": [dict(row) for row in category_breakdown],
            "as_of": datetime.now().isoformat()
        }
    finally:
        await conn.close()

@app.post("/api/test-notification")
async def test_notification(email: Optional[str] = None, phone: Optional[str] = None):
    """Send a test notification"""
    from notifier import NotificationManager

    notifier = NotificationManager()

    test_news = {
        "ticker": "TEST",
        "headline": "This is a test notification from NASDAQ News Scraper",
        "source": "Test",
        "url": "https://example.com",
        "impact_level": "high",
        "sentiment_score": 50,
        "ai_summary": "Test notification to verify alert system is working.",
        "category": "test"
    }

    results = {}

    if email:
        success = await notifier.send_email(email, [test_news])
        results["email"] = "sent" if success else "failed"

    if phone:
        success = await notifier.send_sms(phone, test_news)
        results["sms"] = "sent" if success else "failed"

    return {"test_results": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
