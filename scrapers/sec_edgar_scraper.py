"""
SEC EDGAR Scraper
Scrapes 8-K filings (current reports) from SEC EDGAR
8-K filings contain material events: earnings, M&A, management changes, etc.
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict
import os

# SEC EDGAR uses RSS feeds for recent filings
# Format: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K
# But we'll use the daily indexes for more reliable scraping

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "NASDAQ-News-Scraper contact@example.com")


class SECEdgarScraper:
    """Scraper for SEC EDGAR 8-K filings"""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json"
        }

    async def get_recent_8k_filings(self, ticker: str, days_back: int = 7) -> List[Dict]:
        """
        Get recent 8-K filings for a ticker.
        8-K = Current Report (material events must be disclosed within 4 business days)
        """
        filings = []

        # EDGAR search URL for 8-K filings
        base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": ticker,
            "type": "8-K",
            "dateb": "",
            "owner": "exclude",
            "count": "10",
            "output": "atom"  # RSS format
        }

        try:
            async with self.session.get(
                base_url,
                params=params,
                headers=self.headers,
                timeout=15
            ) as resp:
                if resp.status != 200:
                    print(f"SEC EDGAR returned {resp.status} for {ticker}")
                    return filings

                content = await resp.text()

                # Parse Atom feed
                try:
                    root = ET.fromstring(content)
                except ET.ParseError:
                    # EDGAR sometimes returns HTML instead of Atom
                    return filings

                # Atom namespace
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                for entry in root.findall("atom:entry", ns):
                    title_elem = entry.find("atom:title", ns)
                    link_elem = entry.find("atom:link", ns)
                    updated_elem = entry.find("atom:updated", ns)
                    summary_elem = entry.find("atom:summary", ns)

                    if title_elem is None or link_elem is None:
                        continue

                    title = title_elem.text or ""
                    link = link_elem.get("href", "")
                    updated_text = updated_elem.text if updated_elem is not None else None

                    # Parse date
                    published = None
                    if updated_text:
                        try:
                            published = datetime.fromisoformat(updated_text.replace("Z", "+00:00")).replace(tzinfo=None)
                        except:
                            pass

                    if published and published < datetime.now() - timedelta(days=days_back):
                        continue

                    # Extract items from 8-K (what material event type)
                    items = self._extract_8k_items(title)

                    # Only include significant items
                    if items and self._is_significant_8k(items):
                        filings.append({
                            "ticker": ticker,
                            "headline": f"SEC 8-K Filing: {title}",
                            "source": "SEC EDGAR",
                            "url": link,
                            "published_at": published or datetime.now(),
                            "raw_content": summary_elem.text if summary_elem is not None else "",
                            "sec_items": items,
                            "filing_type": "8-K"
                        })

        except asyncio.TimeoutError:
            print(f"Timeout fetching SEC filings for {ticker}")
        except Exception as e:
            print(f"Error fetching SEC filings for {ticker}: {e}")

        return filings

    def _extract_8k_items(self, title: str) -> List[str]:
        """
        Extract 8-K item numbers from title.
        Common significant items:
        - Item 1.01: Entry into Material Definitive Agreement
        - Item 1.02: Termination of Material Definitive Agreement
        - Item 1.03: Bankruptcy/Receivership
        - Item 2.01: Completion of Acquisition/Disposition
        - Item 2.02: Results of Operations (earnings)
        - Item 2.05: Costs Associated with Exit/Disposal Activities (layoffs)
        - Item 4.01: Changes in Certifying Accountant
        - Item 5.01: Changes in Control of Registrant
        - Item 5.02: Departure of Directors/Officers
        - Item 5.03: Amendments to Articles of Incorporation
        - Item 8.01: Other Events (catch-all for material news)
        """
        import re
        items = re.findall(r'Item\s+([\d\.]+)', title)
        return items

    def _is_significant_8k(self, items: List[str]) -> bool:
        """
        Determine if 8-K items are significant for trading.
        Filter out routine filings.
        """
        significant_items = {
            "1.01", "1.02", "1.03",  # Agreements, bankruptcy
            "2.01", "2.02", "2.03", "2.04", "2.05", "2.06",  # MA, earnings, layoffs
            "3.01", "3.02", "3.03",  # Delisting, unregistered sales
            "4.01", "4.02",  # Auditor changes
            "5.01", "5.02", "5.03", "5.04", "5.05", "5.06", "5.07", "5.08",  # Management changes
            "6.01", "6.02", "6.03", "6.04", "6.05",  # Asset-backed securities
            "7.01",  # Regulation FD (selective disclosure)
            "8.01",  # Other material events
        }

        return any(item in significant_items for item in items)

    def classify_sec_impact(self, items: List[str], headline: str) -> tuple:
        """
        Classify SEC filing impact and category.
        Returns (impact_level, category)
        """
        headline_lower = headline.lower()

        # High impact items
        high_impact_items = {"1.01", "1.03", "2.01", "5.01", "5.02", "5.07"}

        # Medium impact
        medium_impact_items = {"2.02", "2.05", "7.01", "8.01"}

        if any(item in high_impact_items for item in items):
            impact = "high"
        elif any(item in medium_impact_items for item in items):
            impact = "medium"
        else:
            impact = "low"

        # Category classification
        category = "sec"
        if any(x in headline_lower for x in ["earnings", "eps", "revenue", "quarterly"]):
            category = "earnings"
        elif any(x in headline_lower for x in ["acquisition", "merger", "acquire", "buy"]):
            category = "ma"
        elif any(x in headline_lower for x in ["ceo", "executive", "officer", "director", "resign"]):
            category = "management"
        elif any(x in headline_lower for x in ["layoff", "workforce", "employee", "restructuring"]):
            category = "workforce"

        return impact, category


async def test_sec_scraper():
    """Test SEC scraper"""
    async with aiohttp.ClientSession() as session:
        scraper = SECEdgarScraper(session)
        filings = await scraper.get_recent_8k_filings("AAPL", days_back=30)
        print(f"Found {len(filings)} 8-K filings for AAPL")
        for f in filings[:3]:
            print(f"  - {f['headline'][:80]}...")
            print(f"    Items: {f.get('sec_items', [])}")


if __name__ == "__main__":
    asyncio.run(test_sec_scraper())
