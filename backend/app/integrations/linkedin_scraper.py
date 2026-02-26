"""Browser-based LinkedIn scraping integration.

Uses Playwright to scrape LinkedIn profiles with authentication support.
Extracts profile data, skills, experience, and recent activity.
"""
import asyncio
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

logger = structlog.get_logger()


class LinkedInBrowserScraper:
    """
    Scrapes LinkedIn profiles using headless browser with authentication.
    
    Extracts:
    - Profile info (name, headline, location)
    - Experience (roles, companies, tenure)
    - Skills (all, not just top 3)
    - Recent posts/activity (with auth)
    - Education
    """
    
    def __init__(self, headless: bool = True, li_at_cookie: Optional[str] = None):
        self.headless = headless
        self._browser: Optional[Browser] = None
        # Load li_at from settings if not provided
        if li_at_cookie is None:
            from app.config import settings
            self.li_at_cookie = settings.linkedin_cookie  # uses LINKEDIN_LI_AT or PHANTOMBUSTER_LI_AT
        else:
            self.li_at_cookie = li_at_cookie
        
        if self.li_at_cookie:
            logger.info("LinkedIn cookie loaded", cookie_length=len(self.li_at_cookie), cookie_prefix=self.li_at_cookie[:8])
        else:
            logger.warning("No LinkedIn li_at cookie configured - will use public/SerpAPI fallback only")
    
    async def scrape_profile(self, linkedin_url: str) -> Dict[str, Any]:
        """
        Scrape a LinkedIn profile with authenticated access or public fallback.
        
        Args:
            linkedin_url: LinkedIn profile URL
            
        Returns:
            Structured profile data including posts and activity
        """
        is_authenticated = bool(self.li_at_cookie)
        logger.info("Starting LinkedIn scrape", url=linkedin_url, authenticated=is_authenticated)
        
        # Try authenticated scraping first if cookie is available
        if is_authenticated:
            try:
                result = await self._scrape_authenticated(linkedin_url)
                if result.get("success"):
                    return result
                logger.warning("Authenticated scraping failed, trying public fallback")
            except Exception as e:
                logger.warning("Authenticated scraping error, trying public fallback", error=str(e)[:100])
        
        # Fall back to public scraping (no authentication)
        return await self._scrape_public(linkedin_url)
    
    async def _scrape_authenticated(self, linkedin_url: str) -> Dict[str, Any]:
        """Scrape with authentication cookies."""
        # Ensure HTTPS (LinkedIn redirects http to https but cookies need https)
        linkedin_url = linkedin_url.replace("http://", "https://")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            
            # Inject LinkedIn session cookies
            cookies_to_add = [
                {
                    "name": "li_at",
                    "value": self.li_at_cookie,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                },
                {
                    "name": "JSESSIONID",
                    "value": f'"ajax:{self.li_at_cookie[:20]}"',
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                },
            ]
            await context.add_cookies(cookies_to_add)
            logger.info("Injected LinkedIn session cookies for authenticated access")
            
            page = await context.new_page()
            
            try:
                # Go directly to the profile page
                await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(4)  # Wait for React to hydrate
                
                # Check if we're on a real profile page or still on login wall
                current_url = page.url
                page_title = await page.title()
                logger.info("Page loaded", url=current_url, title=page_title[:100])
                
                # Check for auth wall
                if "authwall" in current_url or "login" in current_url or "signup" in current_url:
                    logger.warning("Hit LinkedIn auth wall despite cookie - cookie may be expired", url=current_url)
                    return {"success": False, "error": "Auth wall hit - cookie may be expired"}
                
                # Scroll to load lazy content
                await self._scroll_page(page)
                await asyncio.sleep(2)
                
                # Get FULL page text (larger for LLM)
                page_text = await self._get_page_text(page)
                logger.info("Page text captured", length=len(page_text), url=linkedin_url)
                
                # Extract structured data using multiple strategies
                profile = await self._extract_profile_data(page, page_text)
                experience = await self._extract_experience(page, page_text)
                education = await self._extract_education(page, page_text)
                skills = await self._extract_skills(page, page_text)
                activity = await self._extract_activity(page, linkedin_url)
                
                # If selectors failed but we have page_text, mark success anyway
                # The LLM analysis will extract data from page_text_preview
                has_any_data = bool(page_text and len(page_text) > 500)
                
                if not has_any_data:
                    logger.warning("No usable page text captured - may need longer wait", url=linkedin_url)
                    return {"success": False, "error": "No page content captured"}
                
                result = {
                    "success": True,
                    "source": "browser_scrape_authenticated",
                    "scraped_at": datetime.utcnow().isoformat(),
                    "profile": profile,
                    "experience": experience,
                    "education": education,
                    "skills": skills,
                    "activity": activity,
                    "linkedin_url": linkedin_url,
                    # Pass full text for LLM (increased from 2000 to 8000)
                    "page_text_preview": page_text[:8000] if page_text else "",
                }
                
                logger.info(
                    "Authenticated LinkedIn scrape complete",
                    url=linkedin_url,
                    has_name=bool(profile.get("name")),
                    experience_count=len(experience),
                    skills_count=len(skills),
                    page_text_length=len(page_text),
                )
                return result
                
            except Exception as e:
                logger.error("Authenticated scrape failed", url=linkedin_url, error=str(e)[:200])
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()

    
    async def _scrape_public(self, linkedin_url: str) -> Dict[str, Any]:
        """Scrape public LinkedIn profile without authentication."""
        logger.info("Starting public LinkedIn scrape", url=linkedin_url)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )
            
            page = await context.new_page()
            
            try:
                # Navigate directly to profile
                await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                
                # Get page text and title
                page_text = await self._get_page_text(page)
                page_title = await page.title()
                
                # Extract what we can from public page (auth wall shows basic info)
                profile = await self._extract_public_profile_data(page, page_text, page_title)
                
                result = {
                    "success": True,
                    "source": "browser_scrape_public",
                    "scraped_at": datetime.utcnow().isoformat(),
                    "profile": profile,
                    "experience": [],  # Not available publicly
                    "education": [],
                    "skills": [],
                    "activity": [],
                    "linkedin_url": linkedin_url,
                    "page_text_preview": page_text[:2000] if page_text else "",
                }
                
                logger.info("Public LinkedIn scrape complete", url=linkedin_url)
                return result
                
            except PlaywrightTimeout as e:
                logger.error("Public scrape timeout", url=linkedin_url, error=str(e))
                return {"success": False, "error": "Timeout loading profile"}
            except Exception as e:
                logger.error("Public scrape failed", url=linkedin_url, error=str(e))
                return {"success": False, "error": str(e)}
    
    async def _scroll_page(self, page: Page) -> None:
        """Scroll through page to load all content."""
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.5)
        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
    
    async def _get_page_text(self, page: Page) -> str:
        """Get all visible text from the page."""
        try:
            # Get the main content text
            text = await page.evaluate("""
                () => {
                    // Remove script and style elements
                    const clone = document.body.cloneNode(true);
                    const scripts = clone.querySelectorAll('script, style, noscript');
                    scripts.forEach(s => s.remove());
                    return clone.innerText;
                }
            """)
            return text or ""
        except Exception as e:
            logger.warning("Error getting page text", error=str(e))
            return ""
    
    async def _extract_profile_data(self, page: Page, page_text: str) -> Dict[str, Any]:
        """Extract basic profile information."""
        profile = {}
        
        # Check if we hit an auth wall
        auth_wall_indicators = [
            "Grow your professional network",
            "Sign in to LinkedIn",
            "Join now",
            "Sign in",
            "authwall"
        ]
        
        for indicator in auth_wall_indicators:
            if indicator.lower() in page_text.lower()[:500]:
                logger.warning("Auth wall detected, extracting from page text")
                break
        
        try:
            # Try to extract name from page text patterns first
            # LinkedIn public profiles have "Name\nHeadline" pattern
            # Improved patterns to handle names with suffixes (III, Jr, Sr) and certifications
            name_patterns = [
                # Match names with optional suffixes and certifications: "William Palmisano III, AHFI, CFE"
                r'^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+(?:\s+(?:III|II|IV|Jr\.?|Sr\.?))?(?:,\s*[A-Z]+)*)\n',
                # Match name followed by title keywords
                r'\n([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+(?:\s+(?:III|II|IV|Jr\.?|Sr\.?))?(?:,\s*[A-Z]+)*)\n(?:Founder|CEO|CTO|President|VP|Director|Manager|Head)',
                # Simple name pattern as fallback
                r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\n',
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, page_text)
                if match:
                    name = match.group(1).strip()
                    # Validate: not too long, not LinkedIn boilerplate text
                    if len(name) < 80 and "professional" not in name.lower() and "linkedin" not in name.lower() and "join" not in name.lower():
                        profile["name"] = name
                        break
            
            # Try multiple selector strategies for name
            if not profile.get("name"):
                name_selectors = [
                    "h1",
                    ".top-card-layout__title",
                    "[data-anonymize='person-name']",
                    ".text-heading-xlarge",
                    ".pv-text-details__left-panel h1",
                ]
                for selector in name_selectors:
                    try:
                        elem = await page.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            # Validate it's a real name - allow longer names with certifications
                            if text and len(text) < 100:
                                text_lower = text.lower()
                                # Skip LinkedIn boilerplate
                                if "professional" not in text_lower and "network" not in text_lower and "join" not in text_lower and "sign in" not in text_lower:
                                    profile["name"] = text.strip()
                                    break
                    except:
                        continue
            
            # Headline - try selectors and page text
            headline_selectors = [
                ".top-card-layout__headline",
                ".text-body-medium.break-words",
                "[data-anonymize='headline']",
            ]
            for selector in headline_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.inner_text()
                        if text and len(text) < 300 and "Sign in" not in text:
                            profile["headline"] = text.strip()
                            break
                except:
                    continue
            
            # Try to find headline from page text if still missing
            if not profile.get("headline") and profile.get("name"):
                # Look for headline after name
                name = profile["name"]
                headline_match = re.search(rf'{re.escape(name)}\n+(.+?)(?:\n|$)', page_text)
                if headline_match:
                    headline = headline_match.group(1).strip()
                    if len(headline) < 200:
                        profile["headline"] = headline
            
            # Location
            location_selectors = [
                ".top-card-layout__first-subline",
                ".text-body-small.inline.t-black--light.break-words",
                "[data-anonymize='location']",
            ]
            for selector in location_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.inner_text()
                        if text and len(text) < 100:
                            profile["location"] = text.strip()
                            break
                except:
                    continue
            
            # Try to extract followers from page text
            followers_match = re.search(r'([\d,.]+[KMB]?)\s*followers', page_text, re.IGNORECASE)
            if followers_match:
                profile["followers"] = followers_match.group(1)
            
            # About section - try to find it in page text
            about_match = re.search(r'About\n+(.+?)(?=\n\n|\nExperience|\nEducation|$)', page_text, re.DOTALL)
            if about_match:
                about_text = about_match.group(1).strip()
                if len(about_text) > 20:
                    profile["about"] = about_text[:1000]
                    
        except Exception as e:
            logger.warning("Error extracting profile data", error=str(e))
        
        return profile
    
    async def _extract_experience(self, page: Page, page_text: str) -> List[Dict[str, Any]]:
        """Extract work experience from page text."""
        experiences = []
        
        try:
            # Find Experience section in page text
            exp_match = re.search(r'Experience\n+(.+?)(?=\nEducation|\nSkills|\nLicenses|\nVolunteer|$)', 
                                  page_text, re.DOTALL | re.IGNORECASE)
            
            if exp_match:
                exp_text = exp_match.group(1)
                
                # Split by common role patterns
                # Look for patterns like "Title\nCompany\nDates"
                lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
                
                i = 0
                while i < len(lines) and len(experiences) < 10:
                    line = lines[i]
                    
                    # Skip navigation elements
                    if line in ['Show all', 'Show more', 'See more', 'See all']:
                        i += 1
                        continue
                    
                    # Check if this looks like a job title
                    if self._looks_like_job_title(line):
                        exp = {"title": line}
                        
                        # Next line might be company
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if not self._looks_like_date(next_line):
                                exp["company"] = next_line
                                i += 1
                        
                        # Look for duration
                        for j in range(i + 1, min(i + 4, len(lines))):
                            if self._looks_like_date(lines[j]):
                                exp["duration"] = lines[j]
                                break
                        
                        if exp.get("title"):
                            experiences.append(exp)
                    
                    i += 1
                    
        except Exception as e:
            logger.warning("Error extracting experience", error=str(e))
        
        return experiences
    
    def _looks_like_job_title(self, text: str) -> bool:
        """Check if text looks like a job title."""
        title_keywords = [
            'CEO', 'CTO', 'CFO', 'COO', 'Chief', 'President', 'Founder', 'Co-Founder',
            'VP', 'Vice President', 'Director', 'Head', 'Manager', 'Lead', 'Senior',
            'Engineer', 'Developer', 'Designer', 'Analyst', 'Consultant', 'Advisor',
            'Partner', 'Associate', 'Specialist', 'Coordinator', 'Professor', 'Scientist',
            'Chairman', 'Executive', 'Principal', 'General Partner', 'Managing'
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in title_keywords) and len(text) < 100
    
    def _looks_like_date(self, text: str) -> bool:
        """Check if text looks like a date range."""
        date_patterns = [
            r'\d{4}', r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec',
            r'Present', r'yr', r'mo', r'year', r'month'
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in date_patterns)
    
    async def _extract_education(self, page: Page, page_text: str) -> List[Dict[str, Any]]:
        """Extract education from page text."""
        education = []
        
        try:
            edu_match = re.search(r'Education\n+(.+?)(?=\nSkills|\nLicenses|\nVolunteer|\nActivity|$)', 
                                  page_text, re.DOTALL | re.IGNORECASE)
            
            if edu_match:
                edu_text = edu_match.group(1)
                lines = [l.strip() for l in edu_text.split('\n') if l.strip()]
                
                # University names often contain these
                uni_keywords = ['University', 'College', 'Institute', 'School', 'Academy', 'MIT', 'Harvard', 'Stanford', 'Berkeley']
                
                i = 0
                while i < len(lines) and len(education) < 5:
                    line = lines[i]
                    
                    if any(kw in line for kw in uni_keywords):
                        edu = {"school": line}
                        
                        # Next line might be degree
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if 'PhD' in next_line or 'Master' in next_line or 'Bachelor' in next_line or 'BS' in next_line or 'MS' in next_line or 'MBA' in next_line:
                                edu["degree"] = next_line
                        
                        education.append(edu)
                    
                    i += 1
                    
        except Exception as e:
            logger.warning("Error extracting education", error=str(e))
        
        return education
    
    async def _extract_skills(self, page: Page, page_text: str) -> List[str]:
        """Extract skills from page text."""
        skills = []
        
        try:
            skills_match = re.search(r'Skills\n+(.+?)(?=\nRecommendations|\nHonors|\nInterests|$)', 
                                     page_text, re.DOTALL | re.IGNORECASE)
            
            if skills_match:
                skills_text = skills_match.group(1)
                lines = [l.strip() for l in skills_text.split('\n') if l.strip()]
                
                for line in lines[:20]:
                    # Skip common non-skill text
                    if line in ['Show all', 'See all', 'endorsements', 'Endorsed by'] or len(line) > 50:
                        continue
                    if re.match(r'^\d+', line):  # Skip numbers
                        continue
                    if 'endorsement' in line.lower():
                        continue
                    
                    skills.append(line)
                    
        except Exception as e:
            logger.warning("Error extracting skills", error=str(e))
        
        return skills[:15]  # Limit to top 15
    
    async def _extract_activity(self, page: Page, profile_url: str) -> List[Dict[str, Any]]:
        """Extract recent posts and activity."""
        activity = []
        
        try:
            # Navigate to activity page
            activity_url = profile_url.rstrip("/") + "/recent-activity/all/"
            await page.goto(activity_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            
            # Scroll to load posts
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(0.5)
            
            # Get page text and parse posts
            page_text = await self._get_page_text(page)
            
            # Look for post patterns
            # Posts often have engagement metrics like "likes" or "comments"
            post_pattern = r'(.{50,500}?)(?:\d+\s*(?:like|reaction|comment|repost))'
            matches = re.findall(post_pattern, page_text, re.IGNORECASE | re.DOTALL)
            
            for match in matches[:10]:
                post_text = match.strip()
                if len(post_text) > 30:
                    activity.append({
                        "text": post_text[:500],
                        "type": "post"
                    })
                    
        except Exception as e:
            logger.warning("Error extracting activity", error=str(e))
        
        return activity
    
    async def _extract_public_profile_data(self, page: Page, page_text: str, page_title: str) -> Dict[str, Any]:
        """Extract basic profile info from public/auth wall page."""
        profile = {}
        
        try:
            # LinkedIn shows basic info in page title: "Name - Job Title at Company | LinkedIn"
            # Example: "Andrew Ng - Founder of DeepLearning.AI; Managing General Partner of AI Fund | LinkedIn"
            if " | LinkedIn" in page_title:
                title_parts = page_title.split(" | LinkedIn")[0]
                
                # Try to extract name and headline
                if " - " in title_parts:
                    parts = title_parts.split(" - ", 1)
                    profile["name"] = parts[0].strip()
                    profile["headline"] = parts[1].strip() if len(parts) > 1 else ""
                else:
                    profile["name"] = title_parts.strip()
                    profile["headline"] = ""
            
            # Also try meta tags which LinkedIn includes for SEO
            try:
                # Get og:title meta tag
                og_title = await page.get_attribute('meta[property="og:title"]', 'content')
                if og_title and not profile.get("name"):
                    profile["name"] = og_title.strip()
                
                # Get og:description (usually contains headline)  
                og_desc = await page.get_attribute('meta[property="og:description"]', 'content')
                if og_desc and not profile.get("headline"):
                    profile["headline"] = og_desc.strip()
                
                # Get twitter:title as fallback
                twitter_title = await page.get_attribute('meta[name="twitter:title"]', 'content')
                if twitter_title and not profile.get("name"):
                    profile["name"] = twitter_title.strip()
                    
            except Exception as e:
                logger.debug("Could not extract meta tags", error=str(e))
            
            # Try to extract from page text
            if not profile.get("name") or not profile.get("headline"):
                # Look for name pattern at start of page
                lines = page_text.split('\n')
                for i, line in enumerate(lines[:20]):
                    line = line.strip()
                    # Name is usually a capitalized line near the top
                    if re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)+$', line) and len(line) < 50:
                        if not profile.get("name"):
                            profile["name"] = line
                        # Next non-empty line might be headline
                        for j in range(i+1, min(i+5, len(lines))):
                            next_line = lines[j].strip()
                            if next_line and len(next_line) > 10 and len(next_line) < 200:
                                if not profile.get("headline"):
                                    profile["headline"] = next_line
                                break
                        break
            
            logger.info("Extracted public profile", name=profile.get("name"), has_headline=bool(profile.get("headline")))
            
        except Exception as e:
            logger.warning("Error extracting public profile data", error=str(e))
        
        return profile



async def scrape_linkedin_profile(linkedin_url: str) -> Dict[str, Any]:
    """
    Convenience function to scrape a LinkedIn profile.
    
    Args:
        linkedin_url: LinkedIn profile URL
        
    Returns:
        Structured profile data
    """
    scraper = LinkedInBrowserScraper(headless=True)
    return await scraper.scrape_profile(linkedin_url)
