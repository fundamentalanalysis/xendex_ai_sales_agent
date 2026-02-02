"""Google Research Agent - structured trigger discovery."""
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio

from app.agents.base import BaseAgent, AgentResult
from app.integrations.scraper import WebScraper


# Structured query templates for trigger discovery
QUERY_TEMPLATES = {
    # Company triggers
    "funding": '"{company}" funding round',
    "acquisition": '"{company}" acquisition OR acquired',
    "layoffs": '"{company}" layoffs OR "hiring freeze"',
    "product_launch": '"{company}" "product launch" OR "new product"',
    "new_exec": '"{company}" "new CIO" OR "new CTO" OR "new VP"',
    "expansion": '"{company}" expansion OR "new office" OR "new market"',
    "partnership": '"{company}" partnership OR "partners with"',
    
    # Job/intent triggers  
    "hiring_sap": 'site:{domain} careers SAP OR ERP',
    "hiring_data": '"{company}" hiring "data engineer" OR "data analyst"',
    "hiring_automation": '"{company}" hiring automation OR RPA',
    "hiring_cloud": '"{company}" hiring cloud OR AWS OR Azure',
    
    # Competitor triggers
    "competitor_mention": '"{company}" "{competitor}"',
}

TRIGGER_ANALYSIS_PROMPT = """Analyze these search results and identify sales triggers.

Company: {company}
Search Query: {query}
Query Type: {query_type}

Search Results:
{results}

For each relevant result, extract:
1. What trigger/signal does this indicate?
2. How recent is this? (recency in days if possible)
3. How confident are you this is accurate? (0-1)
4. What's the sales implication?

Respond in JSON:
{{
    "triggers_found": [
        {{
            "type": "{query_type}",
            "summary": "What happened",
            "recency_days": 30,
            "confidence": 0.8,
            "evidence_url": "...",
            "sales_implication": "What this means for outreach"
        }}
    ],
    "no_triggers": true/false,
    "notes": "Any additional observations"
}}
"""


class GoogleResearchAgent(BaseAgent):
    """
    Performs structured Google searches for trigger discovery:
    - Company triggers (funding, acquisitions, leadership changes)
    - Job/intent triggers (hiring patterns)
    - Competitor triggers (mentions, partnerships)
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scraper = WebScraper()
    
    async def run(
        self,
        company: str,
        domain: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        query_types: Optional[List[str]] = None,
        max_results_per_query: int = 5,
    ) -> Dict[str, Any]:
        """
        Run structured Google searches for a company.
        
        Args:
            company: Company name to research
            domain: Company domain for site: searches
            competitors: List of competitor names to check
            query_types: Specific query types to run (default: all)
            max_results_per_query: Max results per search
            
        Returns:
            Aggregated triggers from all searches
        """
        self._log_start(company=company)
        
        try:
            # Build queries
            queries = self._build_queries(
                company=company,
                domain=domain,
                competitors=competitors or [],
                query_types=query_types,
            )
            
            # Execute searches concurrently
            all_triggers = []
            queries_run = []
            
            for query_type, query in queries:
                results = await self._search_and_analyze(
                    company=company,
                    query=query,
                    query_type=query_type,
                    max_results=max_results_per_query,
                )
                
                queries_run.append({
                    "query": query,
                    "type": query_type,
                })
                
                if results.get("triggers_found"):
                    all_triggers.extend(results["triggers_found"])
            
            # Deduplicate and rank triggers
            unique_triggers = self._deduplicate_triggers(all_triggers)
            ranked_triggers = sorted(
                unique_triggers, 
                key=lambda x: (x.get("confidence", 0), -x.get("recency_days", 999)),
                reverse=True
            )
            
            result = {
                "success": True,
                "company": company,
                "queries_run": queries_run,
                "triggers": ranked_triggers[:10],  # Top 10 triggers
                "trigger_count": len(ranked_triggers),
                "researched_at": datetime.utcnow().isoformat(),
            }
            
            self._log_complete(company=company, triggers=len(ranked_triggers))
            return result
            
        except Exception as e:
            self._log_error(e, company=company)
            return {
                "success": False,
                "error": str(e),
                "company": company,
            }
    
    def _build_queries(
        self,
        company: str,
        domain: Optional[str],
        competitors: List[str],
        query_types: Optional[List[str]],
    ) -> List[tuple]:
        """Build list of (query_type, query_string) tuples."""
        queries = []
        
        # Determine which query types to run
        types_to_run = query_types or list(QUERY_TEMPLATES.keys())
        
        for query_type in types_to_run:
            if query_type not in QUERY_TEMPLATES:
                continue
                
            template = QUERY_TEMPLATES[query_type]
            
            # Skip domain-specific queries if no domain
            if "{domain}" in template and not domain:
                continue
            
            # Skip competitor queries if no competitors
            if "{competitor}" in template and not competitors:
                continue
            
            # Build query
            if "{competitor}" in template:
                # Create one query per competitor
                for competitor in competitors:
                    query = template.format(
                        company=company,
                        domain=domain or "",
                        competitor=competitor,
                    )
                    queries.append((query_type, query))
            else:
                query = template.format(
                    company=company,
                    domain=domain or "",
                )
                queries.append((query_type, query))
        
        return queries
    
    async def _search_and_analyze(
        self,
        company: str,
        query: str,
        query_type: str,
        max_results: int,
    ) -> Dict[str, Any]:
        """Execute search and analyze results with LLM."""
        
        # Perform search (using scraper's search capability)
        try:
            results = await self.scraper.search_google(query, max_results=max_results)
        except Exception as e:
            self.logger.warning("Search failed", query=query, error=str(e))
            return {"triggers_found": [], "error": str(e)}
        
        if not results:
            return {"triggers_found": [], "no_results": True}
        
        # Format results for LLM
        results_text = ""
        for i, result in enumerate(results):
            results_text += f"""
Result {i+1}:
Title: {result.get('title', 'N/A')}
URL: {result.get('url', 'N/A')}
Snippet: {result.get('snippet', 'N/A')}
Date: {result.get('date', 'Unknown')}
"""
        
        # Analyze with LLM
        try:
            analysis = await self.openai_client.chat_json(
                prompt=TRIGGER_ANALYSIS_PROMPT.format(
                    company=company,
                    query=query,
                    query_type=query_type,
                    results=results_text,
                ),
                system="You are a sales intelligence analyst. Identify actionable triggers from search results."
            )
            return analysis
        except Exception as e:
            self.logger.warning("LLM analysis failed", error=str(e))
            return {"triggers_found": [], "error": str(e)}
    
    def _deduplicate_triggers(self, triggers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate triggers based on summary similarity."""
        seen = set()
        unique = []
        
        for trigger in triggers:
            # Create a key from type + summary (simplified)
            key = f"{trigger.get('type', '')}:{trigger.get('summary', '')[:50]}"
            if key not in seen:
                seen.add(key)
                unique.append(trigger)
        
        return unique
