"""Website Analyzer Agent - analyzes your company website."""
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.agents.base import BaseAgent, AgentResult
from app.integrations.scraper import WebScraper


ANALYSIS_PROMPT = """Analyze this company website content and extract:

1. **Services/Offerings**: List all products and services with descriptions
2. **ICP (Ideal Customer Profile)**: Who are their target customers?
3. **Proof Points**: Case studies, testimonials, metrics, awards
4. **Positioning**: Their unique value proposition (1-2 sentences)
5. **Industries Served**: List of industries they work with

Website Content:
{content}

Respond in this JSON format:
{{
    "services": [
        {{"name": "...", "description": "...", "icp_fit": "Best for..."}}
    ],
    "proof_points": [
        {{"title": "...", "outcome": "...", "industry": "...", "metrics": ["..."]}}
    ],
    "positioning": "One or two sentence value proposition",
    "industries_served": ["Industry1", "Industry2"],
    "icp_summary": "Description of ideal customer"
}}
"""


class WebsiteAnalyzerAgent(BaseAgent):
    """
    Analyzes your company website to extract:
    - Services/offerings taxonomy
    - ICP constraints
    - Proof points (case studies, outcomes)
    - Positioning lines
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scraper = WebScraper()
    
    async def run(
        self, 
        url: str,
        include_subpages: bool = True,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """
        Analyze a company website.
        
        Args:
            url: The website URL to analyze
            include_subpages: Whether to crawl important subpages
            max_pages: Maximum number of pages to analyze
            
        Returns:
            Structured analysis of the website
        """
        self._log_start(url=url)
        
        try:
            # Scrape the website
            pages_to_scrape = [url]
            
            if include_subpages:
                # Add common important pages
                important_paths = [
                    "/about", "/services", "/solutions", "/products",
                    "/case-studies", "/customers", "/industries",
                    "/pricing", "/contact"
                ]
                base_url = url.rstrip("/")
                pages_to_scrape.extend([f"{base_url}{path}" for path in important_paths])
            
            # Scrape all pages concurrently
            results = await self.scraper.scrape_multiple(pages_to_scrape[:max_pages])
            
            all_content = []
            scraped_count = 0
            
            for page_url, content in results.items():
                if content:
                    all_content.append(f"--- PAGE: {page_url} ---\n{content}")
                    scraped_count += 1
            
            if not all_content:
                return AgentResult.fail("Could not scrape any content from website").data
            
            combined_content = "\n\n".join(all_content)
            
            # Truncate if too long (for LLM context)
            if len(combined_content) > 30000:
                combined_content = combined_content[:30000] + "\n...[truncated]"
            
            # Analyze with LLM
            analysis = await self.openai_client.chat_json(
                prompt=ANALYSIS_PROMPT.format(content=combined_content),
                system="You are an expert business analyst. Extract structured information from website content."
            )
            
            # Add metadata
            analysis["url"] = url
            analysis["pages_analyzed"] = scraped_count
            analysis["analyzed_at"] = datetime.utcnow().isoformat()
            
            self._log_complete(url=url, pages=scraped_count)
            return analysis
            
        except Exception as e:
            self._log_error(e, url=url)
            return AgentResult.fail(str(e)).data
