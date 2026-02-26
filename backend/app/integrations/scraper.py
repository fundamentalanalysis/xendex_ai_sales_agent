"""Web scraper using BeautifulSoup for website content extraction."""
import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import structlog
import httpx
from bs4 import BeautifulSoup

logger = structlog.get_logger()


class WebScraper:
    """
    Web scraper for extracting content from websites.
    Uses BeautifulSoup for parsing and httpx for async requests.
    """
    
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    
    async def scrape_url(self, url: str) -> Optional[str]:
        """
        Scrape text content from a URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            Extracted text content or None if failed
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self.headers,
            ) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    logger.warning("Failed to fetch URL", url=url, status=response.status_code)
                    return None
                
                # Parse HTML
                soup = BeautifulSoup(response.text, "lxml")
                
                # Remove script and style elements
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                
                # Extract text
                text = soup.get_text(separator="\n", strip=True)
                
                # Clean up whitespace
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                text = "\n".join(lines)
                
                return text
                
        except httpx.TimeoutException:
            logger.warning("Timeout fetching URL", url=url)
            return None
        except Exception as e:
            logger.warning("Error scraping URL", url=url, error=str(e))
            return None
    
    async def scrape_multiple(
        self, 
        urls: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, Optional[str]]:
        """
        Scrape multiple URLs concurrently.
        
        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dict mapping URL to content (or None if failed)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> tuple:
            async with semaphore:
                content = await self.scrape_url(url)
                return url, content
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        return dict(results)
    
    async def extract_structured(self, url: str) -> Dict[str, Any]:
        """
        Extract structured data from a webpage.
        
        Returns:
            Dict with title, description, headings, main_content
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self.headers,
            ) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    return {"error": f"HTTP {response.status_code}"}
                
                soup = BeautifulSoup(response.text, "lxml")
                
                # Extract structured elements
                result = {
                    "url": url,
                    "title": self._get_title(soup),
                    "description": self._get_meta_description(soup),
                    "headings": self._get_headings(soup),
                    "links": self._get_relevant_links(soup, url),
                    "main_content": self._get_main_content(soup),
                }
                
                return result
                
        except Exception as e:
            logger.error("Error extracting structured data", url=url, error=str(e))
            return {"error": str(e)}
    
    def _get_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        return ""
    
    def _get_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description."""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"]
        return ""
    
    def _get_headings(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract all headings."""
        headings = []
        for level in ["h1", "h2", "h3"]:
            for heading in soup.find_all(level):
                headings.append({
                    "level": level,
                    "text": heading.get_text(strip=True),
                })
        return headings[:20]  # Limit
    
    def _get_relevant_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract relevant internal links."""
        links = []
        parsed_base = urlparse(base_url)
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            
            # Skip empty or javascript links
            if not text or href.startswith("javascript:") or href.startswith("#"):
                continue
            
            # Make absolute URL
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Only keep internal links
            if parsed.netloc == parsed_base.netloc:
                # Check if it's a relevant page
                path = parsed.path.lower()
                relevant_paths = [
                    "/about", "/services", "/solutions", "/products",
                    "/case-stud", "/customer", "/industri", "/pricing",
                    "/careers", "/jobs", "/blog", "/news"
                ]
                
                if any(rp in path for rp in relevant_paths):
                    links.append({
                        "url": full_url,
                        "text": text[:100],
                    })
        
        # Deduplicate by URL
        seen = set()
        unique = []
        for link in links:
            if link["url"] not in seen:
                seen.add(link["url"])
                unique.append(link)
        
        return unique[:15]  # Limit
    
    def _get_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main page content."""
        # Remove noise
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            element.decompose()
        
        # Try to find main content area
        main = soup.find("main") or soup.find(id="content") or soup.find(class_="content")
        
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        
        # Clean up
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)[:10000]  # Limit size
    
    async def search_google(
        self, 
        query: str, 
        max_results: int = 5
    ) -> List[Dict[str, str]]:
        """
        Perform a Google search using SerpAPI.
        
        SerpAPI is more reliable than Google Custom Search and easier to configure.
        Get a free API key at https://serpapi.com (100 searches/month free).
        
        Args:
            query: Search query
            max_results: Maximum results to return
            
        Returns:
            List of {url, title, snippet, date} dicts
        """
        from app.config import settings
        
        # Check if SerpAPI key is configured
        serpapi_key = getattr(settings, 'serpapi_key', None)
        
        # SerpAPI is the only search provider used
        if not serpapi_key:
            logger.warning(
                "SERPAPI_KEY not configured - research will be limited"
            )
            return []
        
        try:
            # SerpAPI request
            api_url = "https://serpapi.com/search.json"
            params = {
                "api_key": serpapi_key,
                "q": query,
                "engine": "google",
                "num": max_results,
            }
            
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(api_url, params=params)
                
                # Check for rate limiting or account issues (like out of credits)
                if response.status_code == 429:
                    logger.warning(
                        "SerpAPI Account Exhausted - Out of Credits!",
                        error=response.text[:200]
                    )
                    return []

                if response.status_code != 200:
                    logger.warning(
                        "SerpAPI error",
                        status=response.status_code,
                        response=response.text[:200]
                    )
                    return []
                
                data = response.json()
                
                # Extract organic results
                results = []
                for item in data.get("organic_results", [])[:max_results]:
                    result = {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "date": item.get("date", ""),
                    }
                    results.append(result)
                
                logger.info("SerpAPI search completed", query=query[:50], results=len(results))
                return results
                
        except httpx.TimeoutException:
            logger.warning("SerpAPI timeout", query=query[:50])
            return []
        except Exception as e:
            logger.error("SerpAPI error", query=query[:50], error=str(e))
            return []
    

