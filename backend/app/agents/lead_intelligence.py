"""Lead Intelligence Agent - analyzes lead company website."""
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.agents.base import BaseAgent, AgentResult
from app.integrations.scraper import WebScraper


LEAD_ANALYSIS_PROMPT = """You are generating a structured B2B research report.

Company Name: {domain}
Website: {content_url_hint}

IMPORTANT:
- Use only information relevant to this exact company and website.
- Do NOT mix with companies of similar names.
- If unsure, do NOT invent data.
- Do NOT fabricate funding rounds or acquisitions.
- If data is unavailable, write "Not publicly available".

Generate structured report in this format based on the following website content:
{content}

Respond in this exact JSON format:
{{
    "company_overview": "Brief summary of what they do",
    "industry": "Primary industry",
    "offerings": ["Product 1", "Product 2"],
    "pain_indicators": [
        "Sign 1", "Sign 2"
    ],
    "buying_signals": [
        "Signal 1", "Signal 2"
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
            
            # Scrape all pages in parallel
            scraped_results = await self.scraper.scrape_multiple(pages_to_scrape, max_concurrent=5)
            
            all_content = []
            scraped_count = 0
            careers_content = None
            
            for page_url, content in scraped_results.items():
                if content:
                    all_content.append(f"--- PAGE: {page_url} ---\n{content}")
                    scraped_count += 1
                    
                    # Track careers content separately for job signal analysis
                    if "/careers" in page_url or "/jobs" in page_url:
                        if not careers_content: # Take the first one found
                            careers_content = content
            
            if not all_content:
                self.logger.warning("Website scraping failed - shifting to Heuristic LLM Knowledge Fallback", domain=domain)
                
                # Zero-Shot research based on Domain Name
                fallback_analysis = await self.openai_client.chat_json(
                    prompt=f"""I was unable to scrape the website for {domain}. 
                    Based on your internal knowledge of this company name and domain, provide a high-confidence business analysis.
                    
                    Respond in this exact JSON format:
                    {{
                        "company_overview": "Specific explanation of what {domain} does",
                        "industry": "Primary industry (e.g. Fintech, Cybersecurity, Healthtech)",
                        "offerings": ["Specific product A", "Specific product B"],
                        "pain_indicators": ["Specific pain point 1", "Pain point 2", "Pain point 3"],
                        "buying_signals": ["Specific growth trigger 1", "Specific signal 2"],
                        "tech_stack_hints": ["Salesforce", "AWS", "Snowflake", "Likely CRM", "Likely Cloud Platform"],
                        "gtm_motion": "enterprise/smb/self-serve/hybrid",
                        "company_size_estimate": "startup/small/medium/enterprise",
                        "growth_stage": "early/growth/mature"
                    }}
                    """,
                    system="You are an expert market researcher. Provide specific, company-aligned intelligence. DO NOT use generic placeholders like 'Likely Product 1'. Use your knowledge of the company or industry to name real products/technologies."
                )
                
                # Merge with metadata
                fallback_analysis.update({
                    "success": True,
                    "domain": domain,
                    "pages_analyzed": 0,
                    "is_heuristic": True,
                    "job_signals": {
                        "relevant_roles": [],
                        "hiring_intensity": "low",
                        "tech_focus_areas": []
                    },
                    "analyzed_at": datetime.utcnow().isoformat()
                })
                return fallback_analysis
            
            combined_content = "\n\n".join(all_content)
            
            # Truncate if too long
            if len(combined_content) > 30000:
                combined_content = combined_content[:30000] + "\n...[truncated]"
            
            # Analyze with LLM
            analysis = await self.openai_client.chat_json(
                prompt=LEAD_ANALYSIS_PROMPT.format(
                    domain=domain,
                    content_url_hint=url,
                    content=combined_content
                ),
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
