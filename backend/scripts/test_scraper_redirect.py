import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.integrations.linkedin_scraper import LinkedInBrowserScraper

async def test_scraper():
    scraper = LinkedInBrowserScraper()
    # Attempt without JSESSIONID
    res = await scraper._scrape_authenticated('https://www.linkedin.com/in/ryankcleung')
    print("RES", res)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_scraper())
