"""LinkedIn Agent - analyzes LinkedIn profile for cold email personalization and lead scoring.

Production-ready implementation with:
- Pydantic validation for type safety
- In-memory caching to avoid redundant API calls
- Retry logic with exponential backoff
- Fallback data sources
"""
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import structlog
import httpx
from app.config import settings

from app.agents.base import BaseAgent, AgentResult
from app.schemas.linkedin import LinkedInIntelligence, LeadScore, AuthoritySignals


# Simple in-memory cache with TTL
class ProfileCache:
    """Simple TTL cache for LinkedIn profiles."""
    
    def __init__(self, ttl_hours: int = 24):
        self._cache: Dict[str, tuple[datetime, LinkedInIntelligence]] = {}
        self._ttl = timedelta(hours=ttl_hours)
    
    def get(self, url: str) -> Optional[LinkedInIntelligence]:
        if url in self._cache:
            cached_at, data = self._cache[url]
            if datetime.utcnow() - cached_at < self._ttl:
                return data
            del self._cache[url]  # Expired
        return None
    
    def set(self, url: str, data: LinkedInIntelligence) -> None:
        self._cache[url] = (datetime.utcnow(), data)
    
    def clear(self) -> None:
        self._cache.clear()


# Global cache instance
_profile_cache = ProfileCache(ttl_hours=24)


# Production-grade prompt for cold email intelligence
LINKEDIN_ANALYSIS_PROMPT = """You are a B2B sales intelligence analyst.

Your task is to analyze a LinkedIn profile and extract ONLY the information that is useful
for writing highly personalized cold emails.

Follow these rules strictly:
- Do NOT hallucinate missing information
- Infer carefully where possible and mark inferred fields clearly
- Keep outputs concise, structured, and actionable
- Focus on decision-making, intent, and personalization signals
- Ignore irrelevant personal or social content
- CRITICAL: For 'Current Title', prioritize the most recent role in 'Work Experience' over the 'Headline'. Headlines often contain aspirations (e.g., 'Aspiring Dev') rather than actual jobs.

## INPUT DATA:

### Profile Information:
{profile_data}

### Work Experience:
{experience_data}

### Skills:
{skills_data}

### Recent Posts/Activity:
{activity_data}

---

## EXTRACTION OBJECTIVE

From the given LinkedIn profile data, extract the following categories:

1. Core Identity
2. Authority & Seniority
3. Personalization Signals
4. Company Context
5. Buying Intent Signals
6. Cold Email Hooks
7. Lead Quality Score
8. Email Angle Classification
9. Opening Line Suggestion

---

## SCORING LOGIC

Lead Score (0–100):
+30 → Decision maker role (Director / VP / CXO / Founder)
+20 → Recent activity related to AI / Automation / Growth
+15 → Hiring or scaling signals
+15 → Relevant technology stack mentioned
+10 → Clear pain or transformation language
-20 → No recent activity or vague profile

---

## REQUIRED OUTPUT FORMAT (STRICT JSON)

{{
  "core_identity": {{
    "full_name": "",
    "current_title": "",
    "company": "",
    "industry": "",
    "location": ""
  }},
  "authority_signals": {{
    "seniority_level": "junior | mid | senior | director | vp | c-suite | founder",
    "decision_maker": true | false,
    "budget_authority": "none | small | medium | large | enterprise",
    "years_in_current_role": "",
    "team_responsibility": "",
    "can_authorize_purchase": true | false,
    "reasoning": "Brief explanation of authority assessment"
  }},
  "personalization_signals": {{
    "recent_topics": [],
    "recent_post_summary": "",
    "featured_content": "",
    "keywords_used": [],
    "conversation_starters": []
  }},
  "company_context": {{
    "company_name": "",
    "company_size_estimate": "",
    "growth_phase": "startup | scaling | mature | unknown",
    "hiring_signal": true | false,
    "recent_news": []
  }},
  "buying_intent_signals": {{
    "intent_keywords": [],
    "technology_mentions": [],
    "pain_indicators": [],
    "growth_indicators": [],
    "hiring_indicators": []
  }},
  "skills": {{
    "technical": [],
    "business": [],
    "leadership": []
  }},
  "cold_email_hooks": [
    "Hook 1 based on their role/company",
    "Hook 2 based on their recent activity or interests"
  ],
  "lead_score": {{
    "score": 0,
    "confidence": 0.0,
    "reasoning": "Detailed explanation of score"
  }},
  "email_angle": {{
    "primary": "cost_optimization | speed_efficiency | revenue_growth | risk_compliance | innovation_ai",
    "secondary": "",
    "reasoning": "Why this angle fits"
  }},
  "opening_line": {{
    "line": "A highly personalized opening line (1-2 sentences, no sales pitch)",
    "alternative": "An alternative opening approach"
  }},
  "sales_priority": "low | medium | high | critical"
}}
"""


class LinkedInAgent(BaseAgent):
    """
    Analyzes LinkedIn profile for cold email personalization and lead scoring.
    
    Production features:
    - Pydantic validation for all outputs
    - In-memory caching (24h TTL)
    - Retry logic with exponential backoff
    - Multiple data source fallbacks
    """
    
    def __init__(self, use_cache: bool = True, max_retries: int = 3, **kwargs):
        super().__init__(**kwargs)
        self.use_cache = use_cache
        self.max_retries = max_retries
        self.logger = structlog.get_logger()
    
    async def run(
        self,
        linkedin_url: Optional[str] = None,
        manual_data: Optional[Dict[str, Any]] = None,
        bypass_cache: bool = False,
        lead_title: Optional[str] = None,
        lead_company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a LinkedIn profile with caching and fallbacks.
        
        Args:
            linkedin_url: LinkedIn profile URL
            manual_data: Manually provided LinkedIn data (optional fallback)
            bypass_cache: Force fresh scrape, ignoring cache
            lead_title: Title from lead record (fallback)
            lead_company: Company from lead record (fallback)
            
        Returns:
            Validated LinkedInIntelligence as dict
        """
        self._log_start(linkedin_url=linkedin_url)
        
        try:
            # Check cache first
            if self.use_cache and linkedin_url and not bypass_cache:
                cached = _profile_cache.get(linkedin_url)
                if cached:
                    self.logger.info("Cache hit", linkedin_url=linkedin_url)
                    return cached.model_dump()
            
            # Get profile data with fallbacks
            scraped_data, source = await self._get_data_with_fallback(
                linkedin_url=linkedin_url,
                manual_data=manual_data,
            )
            
            # Detect LinkedIn login wall or empty profile
            profile_name = scraped_data.get("profile", {}).get("name", "") if scraped_data else ""
            profile_headline = scraped_data.get("profile", {}).get("headline", "") if scraped_data else ""
            is_login_wall = profile_name in ["Sign Up", "Join LinkedIn", "LinkedIn", ""] or "sign in" in profile_name.lower()
            is_empty_profile = not profile_headline and not scraped_data.get("experience")
            
            # If scraping fails OR hits login wall, inject HEURISTIC data
            if not scraped_data or not scraped_data.get("success", True) or (is_login_wall and is_empty_profile):
                self.logger.info("Scraping failed or hit auth wall, using HEURISTIC LLM fallback", linkedin_url=linkedin_url)
                
                # Dynamic placeholder generation
                url_slug = linkedin_url.rstrip('/').split('/')[-1] if linkedin_url else "professional"
                
                heuristic_profile = await self.openai_client.chat_json(
                    prompt=f"""I couldn't scrape the LinkedIn profile for {linkedin_url}.
                    Name hint from URL: {url_slug}
                    Title: {lead_title or 'Unknown'}
                    Company: {lead_company or 'Unknown'}
                    
                    Based on this role and company, provide a realistic professional summary and likely focus areas.
                    
                    Respond in JSON:
                    {{
                        "headline": "A realistic professional headline for a {lead_title} at {lead_company}",
                        "name": "Estimated full name from {url_slug}",
                        "about": "A 2-3 sentence professional summary based on this career path",
                        "skills": ["Skill 1", "Skill 2", "Skill 3"],
                        "likely_initiatives": ["Initiative 1", "Initiative 2"],
                        "topics": ["Relevant industry topic 1", "Topic 2"]
                    }}
                    """,
                    system="You are an expert sales intelligence analyst. Generate realistic professional profiles based on limited context."
                )

                scraped_data = {
                    "success": True,
                    "profile": {
                        "headline": heuristic_profile.get("headline"), 
                        "name": heuristic_profile.get("name"),
                        "location": "Location unknown",
                        "about": heuristic_profile.get("about")
                    },
                    "skills": heuristic_profile.get("skills", []), 
                    "experience": [
                        {
                            "title": lead_title or "Professional", 
                            "company": lead_company or "Company", 
                            "duration": "Duration unknown",
                            "description": f"Currently serving as {lead_title} focusing on {', '.join(heuristic_profile.get('topics', []))}"
                        }
                    ],
                    "activity": [{"text": t} for t in heuristic_profile.get("likely_initiatives", [])],
                    "page_text_preview": ""
                }
                source = "heuristic_llm_fallback"

            # Analyze with LLM (with retry)
            analysis = await self._analyze_with_retry(scraped_data)
            
            # Validate with Pydantic
            intelligence = LinkedInIntelligence.from_llm_response(
                analysis,
                success=True,
                source=source,
                linkedin_url=linkedin_url,
                analyzed_at=datetime.utcnow().isoformat(),
                raw_data=scraped_data if source == "browser_scrape" else None,
            )
            
            # Cache the validated result
            if self.use_cache and linkedin_url:
                _profile_cache.set(linkedin_url, intelligence)
            
            self._log_complete(linkedin_url=linkedin_url, source=source)
            return intelligence.model_dump()
            
        except Exception as e:
            self._log_error(e, linkedin_url=linkedin_url)
            return self._error_response(linkedin_url, str(e))
    
    async def _get_data_with_fallback(
        self,
        linkedin_url: Optional[str],
        manual_data: Optional[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], str]:
        """Get profile data with multiple fallback sources."""
        
        # Priority 1: Manual data
        if manual_data:
            return manual_data, "manual"
        
        if not linkedin_url:
            return {}, "none"
        
        # Priority 2: SerpAPI (Reliable & Fast)
        serp_data = await self._scrape_via_serpapi(linkedin_url)
        
        # Accept SerpAPI data ONLY if we have real profile data
        # Reject generic search results like "100+ profiles"
        if serp_data.get("success"):
            profile = serp_data.get("profile", {})
            name = profile.get("name", "")
            headline = profile.get("headline", "")
            experience = serp_data.get("experience", [])
            
            # Validate we got actual profile data, not search result garbage
            has_valid_name = name and not any(x in name.lower() for x in ["100+", "profiles", "search", "results"])
            has_useful_data = headline or len(experience) > 0
            
            if has_valid_name and has_useful_data:
                self.logger.info("SerpAPI data accepted", source=serp_data.get("source"))
                return serp_data, "serpapi"
            else:
                self.logger.warning(
                    "SerpAPI data rejected - insufficient data",
                    name=name,
                    has_headline=bool(headline),
                    experience_count=len(experience)
                )
        
        # Priority 3: Browser scraping
        try:
            from app.integrations.linkedin_scraper import scrape_linkedin_profile
            self.logger.info("Attempting browser scrape", linkedin_url=linkedin_url)
            scraped = await scrape_linkedin_profile(linkedin_url)
            if scraped.get("success"):
                self.logger.info("Browser scrape successful")
                return scraped, "browser_scrape"
        except Exception as e:
            self.logger.warning("Browser scrape failed", error=str(e))
        
        # Priority 4: URL parsing (last resort)
        url_data = {"profile": self._extract_from_url(linkedin_url), "success": True}
        return url_data, "url_parse"
    
    async def _analyze_with_retry(
        self, 
        scraped_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze profile with exponential backoff retry."""
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                analysis = await self._analyze_profile(scraped_data)
                return analysis
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                self.logger.warning(
                    "LLM analysis failed, retrying",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    wait_time=wait_time,
                    error=str(e)
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait_time)
        
        # All retries failed - return basic fallback
        self.logger.error("All LLM retries failed", error=str(last_error))
        return self._fallback_analysis(scraped_data)
    
    def _extract_from_url(self, linkedin_url: str) -> Dict[str, Any]:
        """Extract minimal info from LinkedIn URL."""
        try:
            parts = linkedin_url.rstrip("/").split("/")
            if "in" in parts:
                idx = parts.index("in")
                if idx + 1 < len(parts):
                    username = parts[idx + 1]
                    # Clean up username
                    name = username.replace("-", " ").title()
                    return {"username": username, "name": name}
        except Exception:
            pass
        return {}
    
    async def _analyze_profile(
        self, 
        scraped_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze scraped profile data with LLM for cold email intelligence."""
        
        # Format profile data
        profile = scraped_data.get("profile", {})
        
        # Extract current role from experience (most reliable source)
        experience = scraped_data.get("experience", [])
        current_role = None
        current_company = None
        
        if experience and len(experience) > 0:
            # First item is usually the most recent
            most_recent = experience[0]
            current_role = most_recent.get("title", "")
            current_company = most_recent.get("company", "")
        
        # FALLBACK: If no experience data, try to extract role from headline
        if not current_role and profile.get("headline"):
            headline = profile.get("headline", "")
            # Simple heuristic: "Role at Company"
            if " at " in headline:
                parts = headline.split(" at ")
                current_role = parts[0].strip()
                current_company = parts[1].strip()
            else:
                current_role = headline
        
        # Debug log to see what we actually have
        self.logger.info(
            "Analyzing profile data", 
            name=profile.get("name"),
            headline_len=len(profile.get("headline", "") or ""),
            about_len=len(profile.get("about", "") or ""),
            experience_count=len(experience),
            skills_count=len(scraped_data.get("skills", [])),
            extracted_current_role=current_role
        )

        profile_text = f"""
Name: {profile.get('name', 'Unknown')}
Headline: {profile.get('headline', 'N/A')}
Location: {profile.get('location', 'N/A')}
Followers: {profile.get('followers', 'N/A')}
About: {profile.get('about', 'N/A')}
"""
        
        # Add explicit current role if we found it
        if current_role:
            profile_text += f"\n**CURRENT ROLE (from Work Experience)**: {current_role}"
            if current_company:
                profile_text += f" at {current_company}"
            profile_text += "\nIMPORTANT: Use this as the 'current_title' in your output, NOT the headline.\n"
        
        # Format experience
        experience_text = ""
        for i, exp in enumerate(experience[:8]):
            experience_text += f"{i+1}. {exp.get('title', 'Role')} at {exp.get('company', 'Company')} - {exp.get('duration', 'Duration unknown')}\n"
        if not experience_text:
            experience_text = "No experience data available"
        
        # Format skills
        skills = scraped_data.get("skills", [])
        skills_text = ", ".join(skills[:15]) if skills else "No skills data available"
        
        # Format activity
        activity = scraped_data.get("activity", [])
        activity_text = ""
        for i, post in enumerate(activity[:5]):
            text = post.get("text", "")[:400]
            reactions = post.get("reactions", "0")
            activity_text += f"Post {i+1}: {text}... [Reactions: {reactions}]\n\n"
        if not activity_text:
            activity_text = "No recent activity available"
        
        # Use full page text as primary source when structured selectors returned little data
        # (this is common because LinkedIn's HTML changes frequently)
        page_text = scraped_data.get("page_text_preview", "")
        profile_has_data = bool(
            profile.get("about") or
            len(experience) > 0 or
            len(skills) > 5
        )
        
        if page_text and not profile_has_data:
            # Use raw page text as the primary input — LLM will extract everything from it
            self.logger.info(
                "Using raw page text as primary LLM input (selectors returned limited data)",
                page_text_length=len(page_text),
            )
            analysis = await self.openai_client.chat_json(
                prompt=f"""You are a B2B sales intelligence analyst.

Below is the RAW TEXT scraped from a LinkedIn profile page. Extract all relevant professional information for cold email personalization.

## RAW LINKEDIN PAGE TEXT:
{page_text[:6000]}

Extract the following as JSON:
- core_identity: full_name, current_title, location, industry, years_experience
- authority_signals: seniority_level (junior/mid/senior/vp/director/c-suite/founder), decision_maker (bool), budget_authority (none/low/medium/high)
- personalization_signals: recent_topics (list), recent_post_summary, conversation_hook
- buying_intent_signals: growth_indicators (list), technology_mentions (list), pain_signals (list)
- cold_email_hooks: list of 3 specific personalization hooks from their actual profile
- opening_line: object with "line" key - a specific personalized opening sentence
- lead_score: object with "score" key (0-100 int based on seniority/relevance) and "reasoning" key

Rules:
- Only extract what is clearly in the text. Do NOT hallucinate.
- Be specific — use actual words from their profile for hooks and opening lines.
- If something is not visible in the text, return null or empty list.
""",
                system="You are a B2B sales intelligence analyst. Extract actionable insights from raw LinkedIn profile text. Be specific, factual, and focus on information useful for cold email personalization."
            )
        else:
            # Structured data available - use original prompt
            if page_text:
                activity_text += f"\n\nAdditional Profile Context:\n{page_text[:2000]}"
            
            analysis = await self.openai_client.chat_json(
                prompt=LINKEDIN_ANALYSIS_PROMPT.format(
                    profile_data=profile_text,
                    experience_data=experience_text,
                    skills_data=skills_text,
                    activity_data=activity_text,
                ),
                system="You are a B2B sales intelligence analyst specializing in cold email personalization. Extract actionable insights for highly personalized outreach. Be thorough but objective. Do not hallucinate - only extract what is clearly evident from the data."
            )
        return analysis
    
    def _fallback_analysis(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate basic analysis when LLM fails."""
        profile = scraped_data.get("profile", {})
        skills = scraped_data.get("skills", [])
        headline = profile.get("headline", "")
        
        seniority = self._infer_seniority(headline or "")
        est_score = self._estimate_score(seniority)
        
        return {
            "core_identity": {
                "full_name": profile.get("name"),
                "current_title": headline,
                "location": profile.get("location"),
                "industry": "Unknown"
            },
            "authority_signals": {
                "seniority_level": seniority,
                "decision_maker": seniority in ["c-suite", "founder", "vp", "director"],
                "budget_authority": "medium" if seniority in ["c-suite", "founder", "vp"] else "none",
                "reasoning": f"Fallback analysis - inferred from title '{headline}'"
            },
            "personalization_signals": {
                "recent_topics": [],
                "recent_post_summary": ""
            },
            "company_context": {},
            "buying_intent_signals": {},
            "skills": {"technical": skills[:5], "business": [], "leadership": []},
            "lead_score": {
                "score": est_score, 
                "confidence": 0.5, 
                "reasoning": "Fallback score based on seniority inference"
            },
            "cold_email_hooks": [],
            "opening_line": {"line": None, "alternative": None},
            "sales_priority": self._priority_from_seniority(seniority),
        }
    
    def _error_response(self, linkedin_url: Optional[str], error: str) -> Dict[str, Any]:
        """Generate standardized error response."""
        return {
            "success": False,
            "error": error,
            "linkedin_url": linkedin_url,
            "core_identity": {},
            "authority_signals": {"seniority_level": "unknown", "decision_maker": False},
            "lead_score": {"score": 0, "confidence": 0, "reasoning": f"Error: {error}"},
            "cold_email_hooks": [],
            "sales_priority": "low",
        }
    
    async def run_with_manual_input(
        self,
        role: str,
        company: str,
        seniority: Optional[str] = None,
        recent_topics: Optional[List[str]] = None,
        job_change_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create LinkedIn intelligence from manual input."""
        seniority = seniority or self._infer_seniority(role)
        
        intelligence = LinkedInIntelligence(
            success=True,
            source="manual",
            analyzed_at=datetime.utcnow().isoformat(),
        )
        intelligence.core_identity.current_title = role
        intelligence.core_identity.company = company
        intelligence.authority_signals.seniority_level = seniority
        intelligence.authority_signals.decision_maker = seniority in ["c-suite", "founder", "vp"]
        intelligence.authority_signals.can_authorize_purchase = seniority in ["c-suite", "founder", "vp"]
        intelligence.personalization_signals.recent_topics = recent_topics or []
        intelligence.lead_score.score = self._estimate_score(seniority)
        intelligence.lead_score.confidence = 0.5
        intelligence.sales_priority = self._priority_from_seniority(seniority)
        
        return intelligence.model_dump()
    
    def _infer_seniority(self, role: str) -> str:
        """Infer seniority from role title."""
        role_lower = role.lower()
        
        if any(x in role_lower for x in ["ceo", "cto", "cfo", "coo", "chief", "president"]):
            return "c-suite"
        if any(x in role_lower for x in ["founder", "co-founder", "owner"]):
            return "founder"
        if any(x in role_lower for x in ["vp", "vice president", "svp", "evp"]):
            return "vp"
        if any(x in role_lower for x in ["director", "head of"]):
            return "director"
        if any(x in role_lower for x in ["manager", "lead", "principal", "senior"]):
            return "senior"
        if any(x in role_lower for x in ["associate", "junior", "intern"]):
            return "junior"
        
        return "mid"
    
    def _estimate_score(self, seniority: str) -> int:
        """Estimate lead score from seniority."""
        scores = {
            "c-suite": 80,
            "founder": 85,
            "vp": 70,
            "director": 60,
            "senior": 40,
            "mid": 30,
            "junior": 15,
        }
        return scores.get(seniority, 25)
    
    def _priority_from_seniority(self, seniority: str) -> str:
        """Determine sales priority from seniority."""
        if seniority in ["c-suite", "founder"]:
            return "critical"
        if seniority in ["vp", "director"]:
            return "high"
        if seniority == "senior":
            return "medium"
        return "low"

    async def _scrape_via_serpapi(self, linkedin_url: str) -> Dict[str, Any]:
        """Scrape LinkedIn profile via SerpAPI with Google fallback."""
        if not settings.serpapi_key:
            return {"success": False}
            
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Try specific LinkedIn Profile API first (best data)
                try:
                    resp = await client.get(
                        "https://serpapi.com/search.json",
                        params={
                            "engine": "linkedin_profile",
                            "linkedin_url": linkedin_url,
                            "api_key": settings.serpapi_key
                        }
                    )
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        
                        if "error" not in data and data.get("person"):
                            person = data.get("person", {})
                            
                            # Map to our format
                            profile = {
                                "name": person.get("name"),
                                "headline": person.get("headline"),
                                "location": person.get("location"),
                                "about": person.get("about"),
                                "followers": person.get("followers"),
                            }
                            
                            # Map experiences
                            experience = []
                            for exp in person.get("experience", []):
                                experience.append({
                                    "title": exp.get("title"),
                                    "company": exp.get("company"),
                                    "duration": exp.get("date_range"),
                                    "description": exp.get("description")
                                })
                                
                            return {
                                "success": True,
                                "source": "serpapi_profile",
                                "profile": profile,
                                "experience": experience,
                                "skills": [s.get("name") for s in person.get("skills", [])],
                                "activity": [],
                                "page_text_preview": person.get("about", "")
                            }
                except Exception as e:
                    self.logger.warning("SerpAPI Profile Engine failed", error=str(e))

                # Fallback: Use Google Search API to find the profile
                # This works even if the user doesn't have the LinkedIn Profile plan
                search_query = f"{linkedin_url}"
                resp = await client.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google",
                        "q": search_query,
                        "api_key": settings.serpapi_key,
                        "num": 1
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("organic_results", [])
                    
                    if results:
                        result = results[0]
                        title = result.get("title", "")
                        snippet = result.get("snippet", "")
                        
                        # Extract Name and Headline from Title
                        # Format often: "Name - Headline - Company | LinkedIn"
                        name = ""
                        headline = ""
                        
                        if " - " in title:
                            parts = title.split(" - ")
                            name = parts[0]
                            if len(parts) > 1:
                                headline = parts[1]
                        else:
                            name = title.split("|")[0].strip()
                            
                        return {
                            "success": True,
                            "source": "serpapi_google",
                            "profile": {
                                "name": name,
                                "headline": headline,
                                "about": snippet,
                                "location": ""
                            },
                            "experience": [], # Can't get detailed experience from snippet
                            "skills": [],
                            "activity": [],
                            "page_text_preview": snippet
                        }
                        
        except Exception as e:
            self.logger.warning("SerpAPI scraping failed", error=str(e))
            
        return {"success": False}


# Utility function to clear cache (useful for testing)
def clear_linkedin_cache():
    """Clear the global LinkedIn profile cache."""
    _profile_cache.clear()
