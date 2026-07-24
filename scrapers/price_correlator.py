"""
Price Correlator Module
Fetches price data from Yahoo Finance and correlates with news sentiment
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json


class PriceCorrelator:
    """
    Fetches stock price data and correlates with news events.
    Uses Yahoo Finance API (unofficial but publicly accessible).
    """

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def get_intraday_prices(
        self,
        ticker: str,
        period: str = "5d",
        interval: str = "15m"
    ) -> List[Dict]:
        """
        Get intraday price data for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: "1d", "5d", "1mo", "3mo", "6mo", "1y"
            interval: "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d"

        Returns:
            List of price data points
        """
        # Yahoo Finance chart API
        base_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

        # Calculate timestamps
        end = int(datetime.now().timestamp())

        period_map = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365
        }

        days = period_map.get(period, 5)
        start = end - (days * 24 * 60 * 60)

        params = {
            "period1": start,
            "period2": end,
            "interval": interval,
            "includePrePost": "true",
            "events": "div,splits,earnings"
        }

        try:
            async with self.session.get(
                base_url,
                params=params,
                headers=self.headers,
                timeout=15
            ) as resp:
                if resp.status != 200:
                    print(f"Yahoo Finance returned {resp.status} for {ticker}")
                    return []

                data = await resp.json()

                result = data.get("chart", {}).get("result", [])
                if not result:
                    return []

                chart = result[0]
                meta = chart.get("meta", {})
                timestamps = chart.get("timestamp", [])
                indicators = chart.get("indicators", {})
                quote = indicators.get("quote", [{}])[0]

                prices = []
                for i, ts in enumerate(timestamps):
                    if ts is None:
                        continue

                    price_point = {
                        "timestamp": datetime.fromtimestamp(ts),
                        "open": quote.get("open", [None]*len(timestamps))[i],
                        "high": quote.get("high", [None]*len(timestamps))[i],
                        "low": quote.get("low", [None]*len(timestamps))[i],
                        "close": quote.get("close", [None]*len(timestamps))[i],
                        "volume": quote.get("volume", [None]*len(timestamps))[i]
                    }

                    # Only include valid data points
                    if price_point["close"] is not None:
                        prices.append(price_point)

                return prices

        except asyncio.TimeoutError:
            print(f"Timeout fetching prices for {ticker}")
        except Exception as e:
            print(f"Error fetching prices for {ticker}: {e}")

        return []

    async def get_current_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get current quote data for a ticker.
        """
        base_url = f"https://query1.finance.yahoo.com/v7/finance/quote"

        params = {
            "symbols": ticker,
            "fields": "symbol,shortName,regularMarketPrice,regularMarketChange,"
                      "regularMarketChangePercent,regularMarketVolume,"
                      "fiftyTwoWeekHigh,fiftyTwoWeekLow,"
                      "trailingPE,forwardPE,priceToBook"
        }

        try:
            async with self.session.get(
                base_url,
                params=params,
                headers=self.headers,
                timeout=10
            ) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                results = data.get("quoteResponse", {}).get("result", [])

                if not results:
                    return None

                quote = results[0]
                return {
                    "ticker": quote.get("symbol"),
                    "name": quote.get("shortName"),
                    "price": quote.get("regularMarketPrice"),
                    "change": quote.get("regularMarketChange"),
                    "change_percent": quote.get("regularMarketChangePercent"),
                    "volume": quote.get("regularMarketVolume"),
                    "week_52_high": quote.get("fiftyTwoWeekHigh"),
                    "week_52_low": quote.get("fiftyTwoWeekLow"),
                    "trailing_pe": quote.get("trailingPE"),
                    "forward_pe": quote.get("forwardPE"),
                    "price_to_book": quote.get("priceToBook"),
                    "timestamp": datetime.now()
                }

        except Exception as e:
            print(f"Error fetching quote for {ticker}: {e}")
            return None

    async def get_price_at_time(
        self,
        ticker: str,
        target_time: datetime,
        window_minutes: int = 15
    ) -> Optional[Dict]:
        """
        Get price data closest to a specific time.
        Useful for correlating news events with price movements.
        """
        # Get 1 day of 1-minute data
        prices = await self.get_intraday_prices(ticker, period="1d", interval="1m")

        if not prices:
            return None

        # Find closest price point
        closest = None
        min_diff = timedelta(minutes=window_minutes)

        for price in prices:
            diff = abs(price["timestamp"] - target_time)
            if diff < min_diff:
                min_diff = diff
                closest = price

        return closest

    def calculate_price_change(
        self,
        prices: List[Dict],
        minutes_after: int = 60
    ) -> Optional[float]:
        """
        Calculate price change % in the X minutes after the first data point.
        """
        if len(prices) < 2:
            return None

        start_price = prices[0]["close"]

        # Find price X minutes after
        start_time = prices[0]["timestamp"]
        target_time = start_time + timedelta(minutes=minutes_after)

        end_price = None
        for price in prices:
            if price["timestamp"] >= target_time:
                end_price = price["close"]
                break

        if end_price is None:
            end_price = prices[-1]["close"]

        return ((end_price - start_price) / start_price) * 100

    async def correlate_news_with_price(
        self,
        ticker: str,
        news_time: datetime,
        hours_before: int = 1,
        hours_after: int = 4
    ) -> Dict:
        """
        Correlate a news event with price movement.
        Shows what happened before and after the news.
        """
        # Get price data around the news event
        start_time = news_time - timedelta(hours=hours_before)
        end_time = news_time + timedelta(hours=hours_after)

        # Get 15-minute interval data for the period
        prices = await self.get_intraday_prices(
            ticker,
            period="5d",
            interval="15m"
        )

        if not prices:
            return {"error": "No price data available"}

        # Filter to relevant time window
        window_prices = [
            p for p in prices
            if start_time <= p["timestamp"] <= end_time
        ]

        if len(window_prices) < 2:
            return {"error": "Insufficient price data"}

        # Find price at news time
        news_price = None
        for price in window_prices:
            if price["timestamp"] >= news_time:
                news_price = price["close"]
                break

        if news_price is None:
            news_price = window_prices[-1]["close"]

        # Calculate changes
        pre_news = window_prices[0]["close"]
        post_news = window_prices[-1]["close"]

        change_from_start = ((news_price - pre_news) / pre_news) * 100
        change_after_news = ((post_news - news_price) / news_price) * 100
        total_change = ((post_news - pre_news) / pre_news) * 100

        # Find high/low in window
        highs = [p["high"] for p in window_prices if p["high"]]
        lows = [p["low"] for p in window_prices if p["low"]]

        return {
            "ticker": ticker,
            "news_time": news_time.isoformat(),
            "price_at_news": round(news_price, 2),
            "pre_news_price": round(pre_news, 2),
            "post_news_price": round(post_news, 2),
            "change_before_news_pct": round(change_from_start, 2),
            "change_after_news_pct": round(change_after_news, 2),
            "total_change_pct": round(total_change, 2),
            "high_in_window": round(max(highs), 2) if highs else None,
            "low_in_window": round(min(lows), 2) if lows else None,
            "volume_at_news": window_prices[0].get("volume"),
            "data_points": len(window_prices)
        }

    async def get_multi_ticker_quotes(self, tickers: List[str]) -> List[Dict]:
        """
        Get current quotes for multiple tickers efficiently.
        """
        base_url = "https://query1.finance.yahoo.com/v7/finance/quote"

        # Yahoo allows up to ~100 symbols per request
        chunk_size = 50
        all_quotes = []

        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i + chunk_size]
            symbols = ",".join(chunk)

            params = {"symbols": symbols}

            try:
                async with self.session.get(
                    base_url,
                    params=params,
                    headers=self.headers,
                    timeout=15
                ) as resp:
                    if resp.status != 200:
                        continue

                    data = await resp.json()
                    results = data.get("quoteResponse", {}).get("result", [])
                    all_quotes.extend(results)

            except Exception as e:
                print(f"Error fetching quotes batch: {e}")

            await asyncio.sleep(0.5)  # Be nice to API

        return [
            {
                "ticker": q.get("symbol"),
                "name": q.get("shortName"),
                "price": q.get("regularMarketPrice"),
                "change": q.get("regularMarketChange"),
                "change_percent": q.get("regularMarketChangePercent"),
                "volume": q.get("regularMarketVolume"),
                "market_cap": q.get("marketCap"),
                "timestamp": datetime.now()
            }
            for q in all_quotes
        ]


async def test_price_correlator():
    """Test price correlator"""
    async with aiohttp.ClientSession() as session:
        correlator = PriceCorrelator(session)

        # Test current quote
        print("Fetching NVDA quote...")
        quote = await correlator.get_current_quote("NVDA")
        print(f"Quote: {quote}")

        # Test intraday prices
        print("\nFetching AAPL intraday...")
        prices = await correlator.get_intraday_prices("AAPL", period="1d", interval="15m")
        print(f"Got {len(prices)} price points")
        if prices:
            print(f"Latest: {prices[-1]}")

        # Test correlation
        print("\nTesting correlation...")
        test_time = datetime.now() - timedelta(hours=2)
        correlation = await correlator.correlate_news_with_price("AAPL", test_time)
        print(f"Correlation: {correlation}")


if __name__ == "__main__":
    asyncio.run(test_price_correlator())
