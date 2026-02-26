"""
Test LinkedIn scraping with the actual lead LinkedIn URLs.
"""
import asyncio
import os
import sys
sys.path.append(os.getcwd())

TEST_URLS = [
    ("Kathleen Li (Extend)", "http://www.linkedin.com/in/kathleenliyy"),
    ("Piyush Pathak (Aspire)", "http://www.linkedin.com/in/piyushpathak707"),
]

async def test():
    from app.config import settings
    print(f"Cookie loaded: {len(settings.linkedin_cookie)} chars\n")

    from app.integrations.linkedin_scraper import scrape_linkedin_profile
    
    for name, url in TEST_URLS[:1]:  # Test just first one
        print(f"\n--- Testing: {name} ---")
        print(f"URL: {url}")
        
        result = await scrape_linkedin_profile(url)
        
        print(f"Success: {result.get('success')}")
        print(f"Source: {result.get('source', 'unknown')}")
        
        profile = result.get("profile", {})
        print(f"Name: {profile.get('name', 'N/A')}")
        print(f"Headline: {profile.get('headline', 'N/A')}")
        print(f"Location: {profile.get('location', 'N/A')}")
        print(f"Experience items: {len(result.get('experience', []))}")
        
        page_text = result.get("page_text_preview", "")
        if page_text:
            print(f"\nPage text preview (first 500 chars):")
            print(page_text[:500])
            print("---")
        else:
            print("No page text captured!")

if __name__ == "__main__":
    asyncio.run(test())
