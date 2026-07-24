"""
Enhanced News Scraper Module
Scrapes news from multiple sources and runs AI sentiment analysis
Integrates: Yahoo Finance, SEC EDGAR, Reddit sentiment, Price correlation
"""

import asyncio
import aiohttp
import asyncpg
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict
import os
import re

# Import sub-modules
from sec_edgar_scraper import SECEdgarScraper
from reddit_scraper import RedditScraper
from price_correlator import PriceCorrelator
from notifier import NotificationManager, NotificationConfig

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/nasdaq_news")

# News sources to scrape
NEWS_SOURCES = {
    "yahoo_finance": {
        "type": "rss",
        "url": "https://finance.yahoo.com/rss/headline?s={ticker}",
    }
}

# High-impact keywords for classification
HIGH_IMPACT_KEYWORDS = [
    "earnings", "eps", "revenue", "guidance", "beat", "miss", "outlook",
    "profit", "loss", "quarterly", "q1", "q2", "q3", "q4", "fiscal",
    "acquisition", "merger", "buyout", "takeover", "acquire", "bought",
    "partnership", "deal", "agreement", "contract", "award",
    "fda", "approval", "patent", "lawsuit", "sec", "investigation",
    "settlement", "fine", "violation",
    "ceo", "cfo", "executive", "resigns", "departs", "appointed",
    "board", "director",
    "upgrade", "downgrade", "price target", "analyst", "initiates coverage",
    "overweight", "underweight", "buy rating", "sell rating",
    "bankruptcy", "restructuring", "layoffs", "job cuts", "hiring freeze",
    "stock split", "dividend", "share buyback",
    "ai", "artificial intelligence", "chip", "semiconductor", "data center",
    "cloud", "aws", "azure", "google cloud", "8-k", "filing"
]

MEDIUM_IMPACT_KEYWORDS = [
    "launches", "announces", "introduces", "unveils", "showcases",
    "partnership", "collaboration", "integration", "platform",
    "expansion", "enters market", "new market",
    "investment", "funding", "raises capital",
    "product", "service", "update", "release", "version"
]

CATEGORY_KEYWORDS = {
    "earnings": ["earnings", "eps", "revenue", "guidance", "quarterly", "q1", "q2", "q3", "q4"],
    "analyst": ["upgrade", "downgrade", "price target", "analyst", "rating", "coverage"],
    "sec": ["sec", "filing", "form 8-k", "form 10-k", "form 10-q", "8-k"],
    "product": ["launch", "product", "service", "update", "release"],
    "partnership": ["partnership", "collaboration", "agreement", "deal"],
    "legal": ["lawsuit", "patent", "settlement", "court", "legal"],
    "ma": ["acquisition", "merger", "buyout", "takeover", "acquire"],
    "management": ["ceo", "executive", "officer", "director", "resign", "appointed"],
    "workforce": ["layoff", "workforce", "hiring", "employee"]
}


class NewsScraper:
    def __init__(self):
        self.session = None
        self.db = None
        self.sec_scraper = None
        self.reddit_scraper = None
        self.price_correlator = None
        self.notifier = None

    async def init(self):
        """Initialize connections and sub-scrapers"""
        self.session = aiohttp.ClientSession()
        self.db = await asyncpg.connect(DB_URL)
        self.sec_scraper = SECEdgarScraper(self.session)
        self.reddit_scraper = RedditScraper(self.session)
        self.price_correlator = PriceCorrelator(self.session)
        self.notifier = NotificationManager()

    async def close(self):
        """Cleanup connections"""
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()

    async def analyze_sentiment_groq(self, headline: str, content: str = "") -> tuple:
        """
        Use Groq API for sentiment analysis.
        Returns (sentiment_score, ai_summary)
        """
        if not GROQ_API_KEY:
            return None, None

        prompt = f"""Analyze this financial news for sentiment toward the company.

Headline: {headline}
Content: {content[:500]}

Provide:
1. Sentiment score (-100 extremely negative, 0 neutral, +100 extremely positive)
2. One sentence summary of why this matters to investors
3. Confidence level (high/medium/low)

Respond ONLY in this format:
SCORE: [number]
SUMMARY: [sentence]
CONFIDENCE: [level]"""

        try:
            async with self.session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": "llama-3.2-3b-preview",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 150
                }
            ) as resp:
                data = await resp.json()
                result = data['choices'][0]['message']['content']

                score_match = re.search(r'SCORE:\s*(-?\d+)', result)
                summary_match = re.search(r'SUMMARY:\s*(.+)', result)

                score = int(score_match.group(1)) if score_match else 0
                score = max(-100, min(100, score))
                summary = summary_match.group(1).strip() if summary_match else ""

                return score, summary
        except Exception as e:
            print(f"Groq API error: {e}")
            return None, None

    def analyze_sentiment_heuristic(self, headline: str) -> int:
        """Fallback sentiment analysis using keyword matching"""
        headline_lower = headline.lower()

        positive = [
            "surge", "soar", "jump", "rally", "gain", "rise", "up", "higher",
            "beat", "exceed", "outperform", "upgrade", "buy", "bullish",
            "strong", "growth", "profit", "record", "high", "boost",
            "partnership", "deal", "contract", "approval", "launch",
            "innovation", "breakthrough", "milestone", "expansion"
        ]

        negative = [
            "fall", "drop", "plunge", "decline", "sink", "crash", "down", "lower",
            "miss", "underperform", "downgrade", "sell", "bearish",
            "weak", "loss", "low", "cut", "layoff", "layoffs", "firing",
            "investigation", "lawsuit", "fine", "penalty", "delay",
            "recall", "defect", "problem", "issue", "concern", "warning",
            "bankruptcy", "restructuring", "debt", "dilution"
        ]

        pos_count = sum(1 for word in positive if word in headline_lower)
        neg_count = sum(1 for word in negative if word in headline_lower)

        total = pos_count + neg_count
        if total == 0:
            return 0

        raw_score = ((pos_count - neg_count) / total) * 100
        return int(raw_score)

    def classify_impact(self, headline: str, sec_items: list = None) -> tuple:
        """Classify news impact level and category"""
        headline_lower = headline.lower()

        # Check for high impact (include SEC items)
        if any(kw in headline_lower for kw in HIGH_IMPACT_KEYWORDS):
            impact = "high"
        elif any(kw in headline_lower for kw in MEDIUM_IMPACT_KEYWORDS):
            impact = "medium"
        else:
            impact = "low"

        # If it's an SEC filing with significant items, bump to high
        if sec_items and self.sec_scraper._is_significant_8k(sec_items):
            impact = "high"

        # Classify category
        category = "general"
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in headline_lower for kw in keywords):
                category = cat
                break

        return impact, category

    async def scrape_yahoo_finance(self, ticker: str) -> List[Dict]:
        """Scrape Yahoo Finance RSS for a ticker"""
        url = NEWS_SOURCES["yahoo_finance"]["url"].format(ticker=ticker)
        articles = []

        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return articles

                content = await resp.text()
                feed = feedparser.parse(content)

                for entry in feed.entries[:10]:
                    published = None
                    if hasattr(entry, 'published_parsed'):
                        published = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed'):
                        published = datetime(*entry.updated_parsed[:6])

                    if published and published < datetime.now() - timedelta(days=7):
                        continue

                    articles.append({
                        "ticker": ticker,
                        "headline": entry.title,
                        "source": "Yahoo Finance",
                        "url": entry.link,
                        "published_at": published or datetime.now(),
                        "raw_content": entry.get('summary', ''),
                        "sec_items": None
                    })

        except Exception as e:
            print(f"Error scraping Yahoo for {ticker}: {e}")

        return articles

    async def process_article(self, article: Dict) -> bool:
        """Process a single article: analyze sentiment, classify, save to DB"""
        # Check if already exists
        exists = await self.db.fetchval("""
            SELECT 1 FROM news_items WHERE url = $1
        """, article['url'])

        if exists:
            return False

        # Classify impact
        sec_items = article.get('sec_items')
        impact, category = self.classify_impact(article['headline'], sec_items)

        # Analyze sentiment
        sentiment, summary = None, None

        # Try Groq first for high/medium impact news
        if impact in ["high", "medium"] and GROQ_API_KEY:
            sentiment, summary = await self.analyze_sentiment_groq(
                article['headline'],
                article.get('raw_content', '')
            )

        # Fallback to heuristic
        if sentiment is None:
            sentiment = self.analyze_sentiment_heuristic(article['headline'])
            summary = None

        # Get price correlation if high impact
        price_correlation = None
        if impact == "high":
            try:
                price_correlation = await self.price_correlator.correlate_news_with_price(
                    article['ticker'],
                    article['published_at']
                )
            except Exception as e:
                print(f"Price correlation error: {e}")

        # Save to database
        await self.db.execute("""
            INSERT INTO news_items (
                ticker, headline, source, url, published_at,
                impact_level, sentiment_score, ai_summary, category,
                sec_items, price_correlation, raw_content
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
            article['ticker'],
            article['headline'],
            article['source'],
            article['url'],
            article['published_at'],
            impact,
            sentiment,
            summary,
            category,
            sec_items,
            price_correlation,
            article.get('raw_content', '')
        )

        return True

    async def scrape_ticker(self, ticker: str) -> Dict:
        """Scrape all sources for a ticker"""
        all_articles = []

        # 1. Yahoo Finance
        print(f"  📰 Scraping Yahoo Finance for {ticker}...")
        articles = await self.scrape_yahoo_finance(ticker)
        all_articles.extend(articles)
        await asyncio.sleep(1)

        # 2. SEC EDGAR 8-K filings
        print(f"  📋 Scraping SEC EDGAR for {ticker}...")
        sec_filings = await self.sec_scraper.get_recent_8k_filings(ticker, days_back=7)
        for filing in sec_filings:
            # Classify SEC filings
            items = filing.get('sec_items', [])
            impact, category = self.sec_scraper.classify_sec_impact(items, filing['headline'])
            filing['impact_level'] = impact
            filing['category'] = category
        all_articles.extend(sec_filings)
        await asyncio.sleep(1)

        # 3. Reddit sentiment (for trending tickers)
        print(f"  🔥 Checking Reddit sentiment for {ticker}...")
        reddit_data = await self.reddit_scraper.get_ticker_sentiment([ticker])
        if reddit_data and reddit_data.get('mentions_24h', 0) > 5:
            # Create a synthetic news item for high Reddit activity
            top_post = reddit_data.get('top_posts', [{}])[0]
            if top_post:
                all_articles.append({
                    "ticker": ticker,
                    "headline": f"Reddit Trending: {top_post.get('title', 'High activity on r/wallstreetbets')[:100]}",
                    "source": f"Reddit r/{top_post.get('subreddit', 'wallstreetbets')}",
                    "url": top_post.get('url', ''),
                    "published_at": top_post.get('published_at', datetime.now()),
                    "raw_content": top_post.get('text', ''),
                    "sentiment_score": reddit_data.get('avg_sentiment', 0),
                    "impact_level": "medium" if reddit_data.get('mentions_24h', 0) > 20 else "low",
                    "category": "social",
                    "is_reddit": True
                })
        await asyncio.sleep(0.5)

        # Process all articles
        saved_count = 0
        notified_items = []

        for article in all_articles:
            # Skip if already has sentiment (from Reddit)
            if article.get('is_reddit'):
                saved = await self.save_article_direct(article)
            else:
                saved = await self.process_article(article)

            if saved:
                saved_count += 1
                notified_items.append(article)

        # Send notifications for high-impact items
        if notified_items and NotificationConfig.is_enabled():
            email_recipients = NotificationConfig.get_email_recipients()
            sms_recipients = NotificationConfig.get_sms_recipients()

            if email_recipients or sms_recipients:
                print(f"  📧 Sending notifications for {len(notified_items)} items...")
                await self.notifier.notify_for_news(
                    notified_items,
                    email_recipients=email_recipients,
                    sms_recipients=sms_recipients
                )

        return {
            "ticker": ticker,
            "articles_found": len(all_articles),
            "articles_saved": saved_count
        }

    async def save_article_direct(self, article: Dict) -> bool:
        """Save article that already has processed data"""
        exists = await self.db.fetchval("""
            SELECT 1 FROM news_items WHERE url = $1
        """, article['url'])

        if exists:
            return False

        await self.db.execute("""
            INSERT INTO news_items (
                ticker, headline, source, url, published_at,
                impact_level, sentiment_score, ai_summary, category, raw_content
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            article['ticker'],
            article['headline'],
            article['source'],
            article['url'],
            article['published_at'],
            article.get('impact_level', 'low'),
            article.get('sentiment_score', 0),
            None,
            article.get('category', 'general'),
            article.get('raw_content', '')
        )

        return True

    async def run_scrape_cycle(self, tickers: List[str] = None) -> List[Dict]:
        """Run a full scrape cycle for all tickers"""
        if tickers is None:
            tickers = [
                "QQQ", "TQQQ", "SQQQ", "SOXX",
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                "AMD", "PLTR", "COIN", "RIVN", "LCID", "RKLB", "INTC"
            ]

        print(f"\n{'='*60}")
        print(f"🔍 Starting scrape cycle at {datetime.now()}")
        print(f"📊 Tickers: {len(tickers)}")
        print(f"{'='*60}\n")

        results = []
        for ticker in tickers:
            result = await self.scrape_ticker(ticker)
            results.append(result)
            print(f"✓ {ticker}: {result['articles_found']} found, {result['articles_saved']} saved")
            await asyncio.sleep(2)  # Be nice to APIs

        print(f"\n✅ Scrape cycle complete!")
        return results


async def main():
    """Test the scraper"""
    scraper = NewsScraper()
    await scraper.init()

    try:
        print("🔍 Running enhanced scrape cycle...")
        results = await scraper.run_scrape_cycle(["NVDA", "AAPL", "TSLA"])
        for r in results:
            print(f"  {r['ticker']}: Found {r['articles_found']}, Saved {r['articles_saved']}")
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
