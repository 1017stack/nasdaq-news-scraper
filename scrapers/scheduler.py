"""
Scheduler - Runs scraper every 15 minutes
"""

import asyncio
import schedule
import time
from datetime import datetime
from news_scraper import NewsScraper

async def scrape_job():
    """Run the scraper"""
    print(f"\n[{datetime.now()}] 🚀 Starting scheduled scrape...")

    scraper = NewsScraper()
    await scraper.init()

    try:
        results = await scraper.run_scrape_cycle()
        total_found = sum(r['articles_found'] for r in results)
        total_saved = sum(r['articles_saved'] for r in results)
        print(f"[{datetime.now()}] ✅ Complete: {total_found} found, {total_saved} new articles saved")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error: {e}")
    finally:
        await scraper.close()

def run_async_scrape():
    """Wrapper to run async from schedule"""
    asyncio.run(scrape_job())

def main():
    """Main scheduler loop"""
    print("=" * 60)
    print("NASDAQ News Scraper Scheduler")
    print("Runs every 15 minutes")
    print("=" * 60)

    # Run immediately on startup
    run_async_scrape()

    # Schedule every 15 minutes
    schedule.every(15).minutes.do(run_async_scrape)

    print("\n⏰ Scheduler running. Press Ctrl+C to stop.\n")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Scheduler stopped")
