"""
Reddit Sentiment Scraper
Scrapes r/wallstreetbets and r/stocks for ticker mentions and sentiment
Uses Reddit's JSON API (no auth needed for read-only public data)
"""

import asyncio
import aiohttp
import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import Counter
import os

# Reddit JSON API endpoints (public, no auth needed)
REDDIT_SOURCES = {
    "wallstreetbets": "https://www.reddit.com/r/wallstreetbets/new.json?limit=100",
    "stocks": "https://www.reddit.com/r/stocks/new.json?limit=100",
    "investing": "https://www.reddit.com/r/investing/new.json?limit=50",
    "stockmarket": "https://www.reddit.com/r/StockMarket/new.json?limit=50",
}

REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "NASDAQ-News-Scraper/1.0 (by /u/yourusername)"
)

# Common ticker patterns (avoid false positives)
COMMON_WORDS = {
    "A", "AN", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN", "IS", "IT",
    "ME", "MY", "NO", "OF", "ON", "OR", "OX", "SO", "TO", "UP", "US", "WE",
    "IPO", "CEO", "CFO", "CTO", "COO", "USA", "ETF", "ATH", "ATHS", "LOL",
    "EDIT", "POST", "LMAO", "YOLO", "GDP", "LOL", "FML", "WTF", "TLDR",
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER",
    "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW",
    "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "TWO", "WHO", "BOY", "DID",
    "MAN", "MEN", "PUT", "SAY", "SHE", "TOO", "USE", "WAY", "SINCE",
    "JUST", "LIKE", "OVER", "ALSO", "BACK", "AFTER", "USE", "WORK",
    "FIRST", "WELL", "EVEN", "WANT", "BECAUSE", "THESE", "GIVE", "MOST"
}


class RedditScraper:
    """Scraper for Reddit stock sentiment"""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            "User-Agent": REDDIT_USER_AGENT,
            "Accept": "application/json"
        }

    async def scrape_subreddit(self, subreddit: str, limit: int = 100) -> List[Dict]:
        """
        Scrape recent posts from a subreddit.
        Returns list of post data.
        """
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
        posts = []

        try:
            async with self.session.get(
                url,
                headers=self.headers,
                timeout=15
            ) as resp:
                if resp.status != 200:
                    print(f"Reddit API returned {resp.status} for r/{subreddit}")
                    return posts

                data = await resp.json()

                for child in data.get("data", {}).get("children", []):
                    post = child.get("data", {})

                    # Skip stickied/deleted posts
                    if post.get("stickied") or post.get("removed_by_category"):
                        continue

                    created_utc = post.get("created_utc", 0)
                    published = datetime.fromtimestamp(created_utc)

                    # Skip posts older than 24 hours
                    if published < datetime.now() - timedelta(hours=24):
                        continue

                    posts.append({
                        "title": post.get("title", ""),
                        "text": post.get("selftext", ""),
                        "url": f"https://reddit.com{post.get('permalink', '')}",
                        "published_at": published,
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "upvote_ratio": post.get("upvote_ratio", 0.5),
                        "subreddit": subreddit,
                        "author": post.get("author", "unknown"),
                        "awards": post.get("total_awards_received", 0)
                    })

        except asyncio.TimeoutError:
            print(f"Timeout scraping r/{subreddit}")
        except Exception as e:
            print(f"Error scraping r/{subreddit}: {e}")

        return posts

    def extract_tickers(self, text: str) -> List[str]:
        """
        Extract stock tickers from text.
        Looks for $TICKER or standalone uppercase words 1-5 chars.
        """
        tickers = set()

        # Pattern 1: $TICKER (cashtag format)
        cashtag_pattern = r'\$([A-Z]{1,5})\b'
        for match in re.finditer(cashtag_pattern, text):
            ticker = match.group(1)
            if ticker not in COMMON_WORDS and len(ticker) >= 1:
                tickers.add(ticker)

        # Pattern 2: Standalone uppercase (be more restrictive)
        # Require at least one number or be in known NASDAQ list
        words = re.findall(r'\b[A-Z]{1,5}\b', text)
        for word in words:
            if word not in COMMON_WORDS:
                # Additional validation: should look like ticker
                # Either has number OR is in our default ticker list
                tickers.add(word)

        return list(tickers)

    def analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of Reddit post text.
        Returns score -100 (bearish) to +100 (bullish).
        """
        text_lower = text.lower()

        # Strong bullish indicators
        bullish_strong = [
            "moon", "to the moon", "rocket", "🚀", "tendies", "print", "tendie",
            "all in", "yolo", "calls", "long", "bullish", "bulls", "brrr",
            "breakout", "squeeze", "gamma squeeze", "short squeeze",
            "loading up", "doubling down", "buying the dip", "btfd",
            "undervalued", "hidden gem", "next big", "10x", "100x", "1000x",
            "cant go tits up", "can't go tits up", "cgty"
        ]

        # Moderate bullish
        bullish_moderate = [
            "buy", "buying", "accumulate", "hold", "strong", "good earnings",
            "beat expectations", "growth", "potential", "opportunity",
            "oversold", "recovery", "rebound", "rally", "support", "dip"
        ]

        # Strong bearish
        bearish_strong = [
            "puts", "short", "shorting", "bearish", "bears", "crash",
            "dump", "dumping", "tank", "tanking", "plunge", "collapse",
            "bankruptcy", "going to zero", "bagholder", "bagholders",
            "rug pull", "scam", "ponzi", "overvalued", "bubble", "pump and dump"
        ]

        # Moderate bearish
        bearish_moderate = [
            "sell", "selling", "exit", "avoid", "stay away", "overpriced",
            "weak", "miss", "missed", "disappointment", "concern", "risky",
            "resistance", "overbought", "correction", "pullback", "puts"
        ]

        score = 0

        # Count occurrences
        for phrase in bullish_strong:
            if phrase in text_lower:
                score += 15

        for phrase in bullish_moderate:
            if phrase in text_lower:
                score += 5

        for phrase in bearish_strong:
            if phrase in text_lower:
                score -= 15

        for phrase in bearish_moderate:
            if phrase in text_lower:
                score -= 5

        # Emoji analysis
        bullish_emojis = ["🚀", "📈", "💰", "🤑", "💎", "🙌", "🐂"]
        bearish_emojis = ["📉", "🐻", "💸", "😭", "🤡", "☠️", "💀"]

        for emoji in bullish_emojis:
            score += text.count(emoji) * 10

        for emoji in bearish_emojis:
            score -= text.count(emoji) * 10

        # Clamp to -100, +100
        return max(-100, min(100, score))

    def calculate_post_weight(self, post: Dict) -> float:
        """
        Calculate engagement weight for a post.
        Higher score + more comments = more weight.
        """
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        upvote_ratio = post.get("upvote_ratio", 0.5)
        awards = post.get("awards", 0)

        # Weight formula: log scale to prevent spam from dominating
        import math
        base_weight = math.log10(max(score, 10)) * 10
        comment_weight = math.log10(max(comments, 10)) * 5
        quality_bonus = (upvote_ratio - 0.5) * 20  # Bonus for high upvote ratio
        award_bonus = awards * 2

        return base_weight + comment_weight + quality_bonus + award_bonus

    async def get_ticker_sentiment(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Get aggregated sentiment for specific tickers from Reddit.
        Returns dict of ticker -> sentiment data.
        """
        ticker = tickers[0].upper() if tickers else None  # We'll call per ticker
        if not ticker:
            return {}

        all_posts = []

        # Scrape multiple subreddits
        for subreddit in ["wallstreetbets", "stocks", "investing"]:
            posts = await self.scrape_subreddit(subreddit)
            all_posts.extend(posts)
            await asyncio.sleep(0.5)  # Be nice to Reddit

        # Filter posts mentioning the ticker
        ticker_posts = []
        for post in all_posts:
            combined = f"{post['title']} {post['text']}"
            post_tickers = self.extract_tickers(combined)

            if ticker in post_tickers:
                ticker_posts.append(post)

        if not ticker_posts:
            return {}

        # Calculate weighted sentiment
        total_weight = 0
        weighted_sentiment = 0
        mentions = len(ticker_posts)

        for post in ticker_posts:
            text = f"{post['title']} {post['text']}"
            sentiment = self.analyze_sentiment(text)
            weight = self.calculate_post_weight(post)

            weighted_sentiment += sentiment * weight
            total_weight += weight

        avg_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0

        # Determine sentiment label
        if avg_sentiment > 20:
            sentiment_label = "bullish"
        elif avg_sentiment < -20:
            sentiment_label = "bearish"
        else:
            sentiment_label = "neutral"

        return {
            "ticker": ticker,
            "mentions_24h": mentions,
            "avg_sentiment": round(avg_sentiment, 1),
            "sentiment_label": sentiment_label,
            "top_posts": sorted(ticker_posts, key=lambda x: x["score"], reverse=True)[:3]
        }

    async def get_market_sentiment(self) -> Dict:
        """
        Get overall market sentiment from Reddit.
        Analyzes top posts across subreddits.
        """
        all_posts = []

        for subreddit in ["wallstreetbets", "stocks"]:
            posts = await self.scrape_subreddit(subreddit, limit=50)
            all_posts.extend(posts)

        if not all_posts:
            return {"sentiment": "neutral", "score": 0, "posts_analyzed": 0}

        sentiments = []
        for post in all_posts:
            text = f"{post['title']} {post['text']}"
            sentiment = self.analyze_sentiment(text)
            weight = self.calculate_post_weight(post)
            sentiments.append((sentiment, weight))

        total_weight = sum(w for _, w in sentiments)
        avg_sentiment = sum(s * w for s, w in sentiments) / total_weight if total_weight > 0 else 0

        if avg_sentiment > 30:
            market_sentiment = "very_bullish"
        elif avg_sentiment > 10:
            market_sentiment = "bullish"
        elif avg_sentiment < -30:
            market_sentiment = "very_bearish"
        elif avg_sentiment < -10:
            market_sentiment = "bearish"
        else:
            market_sentiment = "neutral"

        return {
            "sentiment": market_sentiment,
            "score": round(avg_sentiment, 1),
            "posts_analyzed": len(all_posts),
            "timestamp": datetime.now().isoformat()
        }


async def test_reddit_scraper():
    """Test Reddit scraper"""
    async with aiohttp.ClientSession() as session:
        scraper = RedditScraper(session)

        # Test market sentiment
        print("Fetching market sentiment...")
        market = await scraper.get_market_sentiment()
        print(f"Market sentiment: {market}")

        # Test ticker sentiment
        print("\nFetching NVDA sentiment...")
        nvda = await scraper.get_ticker_sentiment(["NVDA"])
        print(f"NVDA: {nvda}")


if __name__ == "__main__":
    asyncio.run(test_reddit_scraper())
