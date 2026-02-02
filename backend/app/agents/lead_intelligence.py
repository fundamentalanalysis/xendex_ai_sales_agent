"""Lead Intelligence Agent - analyzes lead company website."""
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.agents.base import BaseAgent, AgentResult
from app.integrations.scraper import WebScraper


LEAD_ANALYSIS_PROMPT = """Analyze this company website content and extract intelligence for sales outreach:

1. **Company Overview**: What does this company do?
2. **Offerings**: Their main products/services
3. **Pain Indicators**: Signs they might need help (outdated tech mentions, growth challenges, etc.)
4. **Buying Signals**: Indicators they're actively looking (job postings, expansion news, etc.)
5. **Tech Stack Hints**: Any technology mentions
6. **GTM Motion**: How do they sell? (Enterprise, SMB, self-serve, etc.)

Website Content:
{content}

Respond in this JSON format:
{{
    "company_overview": "Brief description of what they do",
    "industry": "Primary industry",
    "offerings": ["Product/Service 1", "Product/Service 2"],
    "pain_indicators": [
        {{"indicator": "...", "evidence": "..."}}
    ],
    "buying_signals": [
        {{"signal": "...", "evidence": "..."}}
    ],
    "tech_stack_hints": ["Technology 1", "Technology 2"],
    "gtm_motion": "enterprise/smb/self-serve/hybrid",
    "company_size_estimate": "startup/small/medium/enterprise",
    "growth_stage": "early/growth/mature"
}}
"""


class LeadIntelligenceAgent(BaseAgent):
    """
    Analyzes lead company website to extract:
    - Industry and offerings
    - Pain indicators
    - Buying signals
    - Tech stack hints
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scraper = WebScraper()
    
    async def run(
        self,
        domain: str,
        include_careers: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze a lead's company website.
        
        Args:
            domain: The company domain to analyze
            include_careers: Whether to check careers page for signals
            
        Returns:
            Structured intelligence about the lead company
        """
        self._log_start(domain=domain)
        
        try:
            # Normalize domain to URL
            url = domain if domain.startswith("http") else f"https://{domain}"
            base_url = url.rstrip("/")
            
            # Pages to analyze
            pages_to_scrape = [
                url,
                f"{base_url}/about",
                f"{base_url}/products",
                f"{base_url}/services",
                f"{base_url}/solutions",
            ]
            
            if include_careers:
                pages_to_scrape.extend([
                    f"{base_url}/careers",
                    f"{base_url}/jobs",
                ])
            
            # Scrape all pages
            all_content = []
            scraped_count = 0
            careers_content = None
            
            for page_url in pages_to_scrape:
                content = await self.scraper.scrape_url(page_url)
                if content:
                    all_content.append(f"--- PAGE: {page_url} ---\n{content}")
                    scraped_count += 1
                    
                    # Track careers content separately for job signal analysis
                    if "/careers" in page_url or "/jobs" in page_url:
                        careers_content = content
            
            if not all_content:
                return {
                    "success": False,
                    "error": "Could not scrape any content from website",
                    "domain": domain,
                }
            
            combined_content = "\n\n".join(all_content)
            
            # Truncate if too long
            if len(combined_content) > 30000:
                combined_content = combined_content[:30000] + "\n...[truncated]"
            
            # Analyze with LLM
            analysis = await self.openai_client.chat_json(
                prompt=LEAD_ANALYSIS_PROMPT.format(content=combined_content),
                system="You are an expert sales intelligence analyst. Extract actionable insights for sales outreach."
            )
            
            # Extract job postings if careers page found
            if careers_content:
                job_signals = await self._extract_job_signals(careers_content)
                analysis["job_signals"] = job_signals
            
            # Add metadata
            analysis["domain"] = domain
            analysis["pages_analyzed"] = scraped_count
            analysis["analyzed_at"] = datetime.utcnow().isoformat()
            analysis["success"] = True
            
            self._log_complete(domain=domain, pages=scraped_count)
            return analysis
            
        except Exception as e:
            self._log_error(e, domain=domain)
            return {
                "success": False,
                "error": str(e),
                "domain": domain,
            }
    
    async def _extract_job_signals(self, careers_content: str) -> List[Dict[str, Any]]:
        """Extract job posting signals from careers page."""
        
        JOB_SIGNAL_PROMPT = """Analyze this careers page content and identify job postings that indicate buying signals.

Look for roles related to:
- IT/Technology leadership
- Digital transformation
- ERP/CRM implementation
- Data/Analytics
- Cloud migration
- Security
- Automation

Careers Page Content:
{content}

Respond in JSON:
{{
    "relevant_roles": [
        {{"title": "...", "department": "...", "signal": "What this indicates about their needs"}}
    ],
    "hiring_intensity": "low/medium/high",
    "tech_focus_areas": ["area1", "area2"]
}}
"""
        
        try:
            # Truncate careers content
            if len(careers_content) > 10000:
                careers_content = careers_content[:10000]
            
            signals = await self.openai_client.chat_json(
                prompt=JOB_SIGNAL_PROMPT.format(content=careers_content),
                system="You are a sales intelligence analyst specializing in intent signals."
            )
            return signals
        except Exception:
            return []
