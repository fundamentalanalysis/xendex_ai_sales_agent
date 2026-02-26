"""
Comprehensive Scoring Engine for AI Sales Agent
Validates and calculates Fit, Readiness, Intent, and Composite Scores
Automatically recalculates on page refresh
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
from app.models.lead import Lead, LeadIntelligence

logger = structlog.get_logger(__name__)


# ==================== DATA MODELS ====================
@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how a score is calculated"""
    category: str
    base_score: float
    components: Dict[str, float]  # component_name -> points_earned
    total_possible: float
    percentage: float
    notes: List[str]


@dataclass
class LeadScores:
    """Complete scoring profile for a lead"""
    fit_score: float
    readiness_score: float
    intent_score: float
    composite_score: float
    fit_breakdown: ScoreBreakdown
    readiness_breakdown: ScoreBreakdown
    intent_breakdown: ScoreBreakdown
    qualification_status: str  # "qualified" or "unqualified"


class SenioritLevel(Enum):
    """Job title seniority classification"""
    ENTRY_LEVEL = "entry"
    MID_LEVEL = "mid"
    SENIOR = "senior"
    EXECUTIVE = "executive"
    FOUNDER = "founder"


class HiringIntensity(Enum):
    """Company hiring intensity classification"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ==================== FIT SCORE CALCULATOR ====================
class FitScoreCalculator:
    """
    Calculates Fit Score (40% weight in composite)
    Max: 100%
    """
    
    MAX_SCORE = 100
    WEIGHT = 0.40
    
    @staticmethod
    def calculate(
        industry_match_score: float,
        company_size: str,
        pain_indicators: int,
        tech_stack_count: int,
        gtm_alignment: bool
    ) -> Tuple[float, ScoreBreakdown]:
        components = {}
        
        # 1. Industry Match (+30% max)
        # industry_match_score is 0 to 2.0. Scale to 30 points.
        industry_score = min(industry_match_score * 15, 30)
        components["Industry Match"] = round(industry_score, 1)
        
        # 2. Company Size (+25% max)
        if company_size == "enterprise":
            size_score = 25
        elif company_size == "medium":
            size_score = 15
        else:  # small
            size_score = 5
        components["Company Size"] = size_score
        
        # 3. Pain Indicators (+25% max - Raised to allow more variance)
        pain_score = min(pain_indicators * 4, 25)
        components["Pain Indicators"] = pain_score
        
        # 4. Tech Stack & GTM (+20% max)
        # Score based on count of technologies
        tech_score = min(tech_stack_count * 2.5, 10)
        gtm_score = 10 if gtm_alignment else 0
        
        components["Tech Stack & GTM"] = tech_score + gtm_score
        
        total = min(sum(components.values()), 100.0)
        percentage = min(total / 100.0, 1.0)
        
        breakdown = ScoreBreakdown(
            category="Fit Score",
            base_score=total,
            components=components,
            total_possible=100,
            percentage=percentage,
            notes=[
                f"Industry similarity score: {industry_match_score}",
                f"Company size: {company_size}",
                f"Pain points identified: {pain_indicators}",
                f"Technology matches: {tech_stack_count}",
                f"GTM alignment: {'✓' if gtm_alignment else '✗'}"
            ]
        )
        
        return percentage, breakdown


# ==================== READINESS SCORE CALCULATOR ====================
class ReadinessScoreCalculator:
    """
    Calculates Readiness Score (30% weight in composite)
    Max: 100%
    """
    
    MAX_SCORE = 100
    WEIGHT = 0.30
    
    @staticmethod
    def calculate(
        buying_signals: int,
        hiring_intensity: HiringIntensity,
        relevant_hiring_roles: int,
        contact_seniority: SenioritLevel,
        job_tenure_days: int
    ) -> Tuple[float, ScoreBreakdown]:
        components = {}
        
        # 1. Website Buying Signals (+40% max - Raised for variance)
        buying_score = min(buying_signals * 8, 40)
        components["Website Buying Signals"] = buying_score
        
        # 2. Hiring Intensity (+20% max)
        hiring_base_score = 0
        hiring_base_score += min(relevant_hiring_roles * 4, 12)
        if hiring_intensity == HiringIntensity.HIGH:
            hiring_base_score += 8
        elif hiring_intensity == HiringIntensity.MEDIUM:
            hiring_base_score += 4
        
        hiring_score = min(hiring_base_score, 20)
        components["Hiring Intensity"] = hiring_score
        
        # 3. Seniority (+25% max)
        if contact_seniority in [SenioritLevel.EXECUTIVE, SenioritLevel.FOUNDER]:
            seniority_score = 25
        elif contact_seniority == SenioritLevel.SENIOR:
            seniority_score = 20
        elif contact_seniority == SenioritLevel.MID_LEVEL:
            seniority_score = 10
        else:
            seniority_score = 0
        components["Contact Seniority"] = seniority_score
        
        # 4. Job Tenure (+20% max) - Only apply for Manager+ roles
        if contact_seniority != SenioritLevel.ENTRY_LEVEL:
            tenure_score = 20 if job_tenure_days < 90 else (10 if job_tenure_days < 180 else 0)
        else:
            tenure_score = 0
        components["Job Tenure"] = tenure_score
        
        total = sum(components.values())
        
        # Guardrail: Cap Junior Readiness at 50
        notes = []
        if contact_seniority == SenioritLevel.ENTRY_LEVEL and total > 50:
            total = 50
            notes.append("Readiness capped at 50% for Junior seniority")
            
        total = min(total, 100.0)
        percentage = total / 100.0
        
        breakdown = ScoreBreakdown(
            category="Readiness Score",
            base_score=total,
            components=components,
            total_possible=100,
            percentage=percentage,
            notes=[
                f"Buying signals detected: {buying_signals}",
                f"Hiring intensity: {hiring_intensity.value}",
                f"Relevant open roles: {relevant_hiring_roles}",
                f"Contact seniority: {contact_seniority.value}",
                f"Days in current role: {job_tenure_days} {'(NEW!)' if job_tenure_days < 90 else '(established)'}",
            ]
        )
        
        return percentage, breakdown


# ==================== INTENT SCORE CALCULATOR ====================
class IntentScoreCalculator:
    """
    Calculates Intent Score (30% weight in composite)
    Max: 100%
    """
    
    MAX_SCORE = 100
    WEIGHT = 0.30
    
    @staticmethod
    def calculate(
        funding_rounds: int,
        new_executives: int,
        expansions: int,
        days_since_news: int,
        linkedin_posts: int,
        strategic_initiatives: int,
        contact_is_exec_founder: bool,
        pain_indicators: int
    ) -> Tuple[float, ScoreBreakdown]:
        components = {}
        
        # 1. Google News Triggers
        news_score = 0
        news_score += funding_rounds * 20
        news_score += new_executives * 15
        news_score += expansions * 12
        
        recency_multiplier = 1.2 if days_since_news <= 30 else 1.0
        news_score = news_score * recency_multiplier
        
        components["Google News Triggers"] = min(news_score, 40)
        
        # 2. LinkedIn Activity
        linkedin_score = 0
        linkedin_score += min(linkedin_posts * 10, 30)
        linkedin_score += min(strategic_initiatives * 10, 30)
        if contact_is_exec_founder:
            linkedin_score += 15
        
        components["LinkedIn Activity"] = min(linkedin_score, 60)
        
        # 3. Pain Continuity (+15% max)
        pain_score = min(pain_indicators * 5, 15)
        components["Pain Continuity"] = pain_score
        
        total = min(sum(components.values()), 100.0)
        percentage = total / 100.0
        
        breakdown = ScoreBreakdown(
            category="Intent Score",
            base_score=total,
            components=components,
            total_possible=100,
            percentage=percentage,
            notes=[
                f"Funding rounds (last 90 days): {funding_rounds}",
                f"New executives: {new_executives}",
                f"Expansion announcements: {expansions}",
                f"Days since news event: {days_since_news} {'(FRESH!)' if days_since_news <= 30 else '(older)'}",
                f"Recent LinkedIn posts: {linkedin_posts}",
                f"Strategic initiatives: {strategic_initiatives}",
                f"Contact level: {'C-Suite/Founder' if contact_is_exec_founder else 'Manager/IC'}",
                f"Pain indicators (continuity): {pain_indicators}"
            ]
        )
        
        return percentage, breakdown


# ==================== COMPOSITE SCORE CALCULATOR ====================
class CompositeScoreCalculator:
    """
    Simplified Dual-Threshold Qualification Model.
    Status = Qualified UNLESS Fit < 30% OR Readiness < 30%.
    Mathematical composite score is disabled.
    """
    @staticmethod
    def calculate(
        fit_score: float,
        readiness_score: float,
        intent_score: float = 0.0,
        qualification_threshold: float = 0.40,
        is_fallback: bool = False,
        previous_status: str = "new"
    ) -> Tuple[float, str]:
        # Qualification Hysteresis: If already qualified, allow a small buffer (5%) 
        # to prevent "flip-flopping" due to minor scraping variance.
        effective_threshold = qualification_threshold
        if previous_status == "qualified":
            effective_threshold = max(0.30, qualification_threshold - 0.05) # 35% buffer if already qualified
            
        # Qualification Rule: Both must pass the effective threshold
        if fit_score >= effective_threshold and readiness_score >= effective_threshold:
            status = "qualified"
        else:
            status = "not_qualified"
            
        # Composite score is removed - returning 0.0
        return 0.0, status


# ==================== MASTER SCORING ENGINE ====================
class MasterScoringEngine:
    def __init__(self, qualification_threshold: float = 0.40):
        self.threshold = qualification_threshold
        self.fit_calc = FitScoreCalculator()
        self.readiness_calc = ReadinessScoreCalculator()
        self.intent_calc = IntentScoreCalculator() # Kept for class compatibility but logic is bypassed
        self.composite_calc = CompositeScoreCalculator()
    
    def calculate_all_scores(
        self,
        industry_match_score: float,
        company_size: str,
        pain_indicators: int,
        tech_stack_count: int,
        gtm_alignment: bool,
        buying_signals: int,
        hiring_intensity: str,
        relevant_hiring_roles: int,
        contact_seniority: str,
        job_tenure_days: int,
        # Following params are legacy from Intent dimension, kept for signature compatibility
        funding_rounds: int = 0,
        new_executives: int = 0,
        expansions: int = 0,
        days_since_news: int = 365,
        linkedin_posts: int = 0,
        strategic_initiatives: int = 0,
        contact_is_exec_founder: bool = False,
        is_fallback: bool = False,
        **extra_kwargs # Catch-all for varied research outputs
    ) -> LeadScores:
        
        # 1. Fit Dimension
        fit_score, fit_breakdown = self.fit_calc.calculate(
            industry_match_score=industry_match_score,
            company_size=company_size,
            pain_indicators=pain_indicators,
            tech_stack_count=tech_stack_count,
            gtm_alignment=gtm_alignment
        )
        
        # 2. Readiness Dimension
        try:
            hiring_val = hiring_intensity.upper() if isinstance(hiring_intensity, str) else "NONE"
            hiring_intensity_enum = HiringIntensity[hiring_val]
        except KeyError:
            hiring_intensity_enum = HiringIntensity.NONE
            
        try:
            seniority_val = contact_seniority.upper() if isinstance(contact_seniority, str) else "MID_LEVEL"
            # Map common variants
            if seniority_val == "MID": seniority_val = "MID_LEVEL"
            if seniority_val == "ENTRY": seniority_val = "ENTRY_LEVEL"
            if seniority_val == "C-SUITE": seniority_val = "EXECUTIVE"
            
            contact_seniority_enum = SenioritLevel[seniority_val]
        except KeyError:
            contact_seniority_enum = SenioritLevel.MID_LEVEL

        readiness_score, readiness_breakdown = self.readiness_calc.calculate(
            buying_signals=buying_signals,
            hiring_intensity=hiring_intensity_enum,
            relevant_hiring_roles=relevant_hiring_roles,
            contact_seniority=contact_seniority_enum,
            job_tenure_days=job_tenure_days
        )
        
        # 3. Intent Dimension (REMOVED - Returning Empty/Neutral)
        intent_score = 0.0
        intent_breakdown = ScoreBreakdown(
            category="Intent Score",
            base_score=0,
            components={},
            total_possible=100,
            percentage=0,
            notes=["Intent dimension disabled per architectural request."]
        )
        
        # 4. Final Qualification (Dual Threshold Model with Hysteresis)
        composite_score, qualification_status = self.composite_calc.calculate(
            fit_score=fit_score,
            readiness_score=readiness_score,
            intent_score=intent_score,
            qualification_threshold=self.threshold,
            is_fallback=is_fallback,
            previous_status=extra_kwargs.get("previous_status", "new")
        )
        
        logger.info(f"Dual-Threshold Scoring - Fit: {fit_score*100}%, Readiness: {readiness_score*100}%, Status: {qualification_status}")
        
        return LeadScores(
            fit_score=fit_score,
            readiness_score=readiness_score,
            intent_score=intent_score,
            composite_score=composite_score,
            fit_breakdown=fit_breakdown,
            readiness_breakdown=readiness_breakdown,
            intent_breakdown=intent_breakdown,
            qualification_status=qualification_status
        )
    
    def validate_scores(
        self,
        lead_scores: LeadScores
    ) -> Dict[str, bool]:
        validations = {
            "fit_in_range": 0.0 <= lead_scores.fit_score <= 1.0,
            "readiness_in_range": 0.0 <= lead_scores.readiness_score <= 1.0,
            "intent_in_range": 0.0 <= lead_scores.intent_score <= 1.0,
            "composite_in_range": 0.0 <= lead_scores.composite_score <= 1.0,
            "composite_formula_correct": True, # Always true now that composite is removed
            "qualification_status_matches": (
                (lead_scores.qualification_status == "qualified" and lead_scores.fit_score >= self.threshold and lead_scores.readiness_score >= self.threshold) or
                (lead_scores.qualification_status == "not_qualified" and (lead_scores.fit_score < self.threshold or lead_scores.readiness_score < self.threshold))
            )
        }
        return validations


class SimpleDataExtractor:
    @staticmethod
    def extract_fit_inputs(lead: Lead, intel: Optional[LeadIntelligence]) -> Dict:
        # Diagnostic logging
        lead_name = getattr(lead, 'company_name', 'Unknown')
        logger.info(f"Extracting FIT inputs for lead: {lead_name}", 
                    industry=getattr(intel, 'industry', 'N/A'),
                    your_inds=getattr(intel, 'your_industries', 'N/A'))

        pain_count = len(intel.lead_pain_indicators) if intel and intel.lead_pain_indicators else 0
        tech_count = len(intel.lead_tech_stack) if intel and intel.lead_tech_stack else 0
        
        # Dynamic Industry Match: 0=No, 1=Partial, 2=Full
        # We use a float here to allow more variance
        industry_score_base = 0.0
        
        lead_ind_source = None
        if intel and intel.industry and intel.industry.lower() != "not publicly available":
            lead_ind_source = intel.industry.lower()
        elif lead.industry:
            lead_ind_source = lead.industry.lower()

        if lead_ind_source:
            if intel and intel.your_industries:
                your_inds = [i.strip().lower() for i in intel.your_industries if i]
                # Full match
                if any(i == lead_ind_source for i in your_inds):
                    industry_score_base = 2.0
                # Cross-Industry broader match (e.g. if we serve Technology, Cybersecurity is a match)
                elif "technology" in your_inds and any(x in lead_ind_source for x in ["software", "cyber", "ai", "platform", "cloud"]):
                    industry_score_base = 1.8
                # Keyword match
                elif any(i in lead_ind_source or lead_ind_source in i for i in your_inds):
                    industry_score_base = 1.5
                # Stem match
                elif any(i[0:4] in lead_ind_source for i in your_inds if len(i) > 4):
                    industry_score_base = 1.2
                else:
                    industry_score_base = 0.5 # Low match instead of zero
            else:
                industry_score_base = 1.0 # Neutral match
        
        # Dynamic Company Size
        company_size = "medium"
        source_size = getattr(intel, 'company_size', None)
        if source_size:
            size_raw = source_size.lower()
            if size_raw != "not publicly available":
                if any(x in size_raw for x in ["enterprise", "large", "5000+", "1000+"]):
                    company_size = "enterprise"
                elif any(x in size_raw for x in ["startup", "small", "seed", "series a"]):
                    company_size = "small"

        # Dynamic GTM Alignment
        gtm_alignment = False
        if intel and intel.gtm_motion:
            gtm_raw = intel.gtm_motion.lower()
            if gtm_raw != "not publicly available":
                if any(x in gtm_raw for x in ["enterprise", "hybrid", "field"]):
                    gtm_alignment = True

        result = {
            "industry_match_score": industry_score_base,
            "company_size": company_size,
            "pain_indicators": pain_count,
            "tech_stack_count": tech_count,
            "gtm_alignment": gtm_alignment
        }
        logger.info(f"FIT Inputs for {lead_name}: {result}")
        return result

    @staticmethod
    def extract_readiness_inputs(lead: Lead, intel: Optional[LeadIntelligence]) -> Dict:
        lead_name = getattr(lead, 'company_name', 'Unknown')
        buying_count = len(intel.lead_buying_signals) if intel and intel.lead_buying_signals else 0
        
        # Heuristic Seniority: Use LinkedIn if researched, else use Lead Persona
        seniority = "mid" # Conservative default: assume mid-level unless proven senior
        if intel and intel.linkedin_seniority and intel.linkedin_seniority.lower() != "not publicly available":
            seniority = intel.linkedin_seniority.lower()
        elif lead.persona or lead.last_name: # Handle some titles mistakenly put in last_name
            p = (lead.persona or "").lower()
            if any(x in p for x in ["director", "head", "lead", "vp", "chief", "executive", "founder", "ceo", "president"]):
                seniority = "senior"
            elif any(x in p for x in ["manager", "principal"]):
                seniority = "mid"

        job_change = 365
        if intel and intel.linkedin_job_change_days is not None:
            job_change = intel.linkedin_job_change_days or 365

        hiring_roles = 0
        if intel and intel.triggers:
            hiring_roles = sum(1 for t in intel.triggers if 'hiring' in t.get('type', '').lower())

        intensity = "LOW"
        if hiring_roles > 3: intensity = "HIGH"
        elif hiring_roles > 0: intensity = "MEDIUM"

        result = {
            "buying_signals": buying_count,
            "hiring_intensity": intensity,
            "relevant_hiring_roles": hiring_roles,
            "contact_seniority": seniority,
            "job_tenure_days": job_change,
        }
        logger.info(f"READINESS Inputs for {lead_name}: {result}")
        return result
        
    @staticmethod
    def extract_intent_inputs(lead: Lead, intel: Optional[LeadIntelligence]) -> Dict:
        lead_name = getattr(lead, 'company_name', 'Unknown')
        funding = 0
        execs = 0
        expansions = 0
        days_since = 365
        
        if intel and intel.triggers:
            for t in intel.triggers:
                t_type = t.get('type', '').lower()
                recency = t.get('recency_days') or 365
                days_since = min(days_since, recency or 365)
                
                if 'funding' in t_type: funding += 1
                elif 'exec' in t_type or 'cio' in t_type: execs += 1
                elif 'expansion' in t_type: expansions += 1
                
        funding = funding or 0
        execs = execs or 0
        expansions = expansions or 0
        days_since = days_since or 365
                
        topics = len(intel.linkedin_topics_30d) if intel and intel.linkedin_topics_30d else 0
        initiatives = len(intel.linkedin_likely_initiatives) if intel and intel.linkedin_likely_initiatives else 0
        
        is_exec = False
        if intel and intel.linkedin_seniority:
            c = intel.linkedin_seniority.lower()
            if 'exec' in c or 'founder' in c or 'c-suite' in c:
                is_exec = True

        pain_count = len(intel.lead_pain_indicators) if intel and intel.lead_pain_indicators else 0

        result = {
            "funding_rounds": funding,
            "new_executives": execs,
            "expansions": expansions,
            "days_since_news": days_since,
            "linkedin_posts": topics,
            "strategic_initiatives": initiatives,
            "contact_is_exec_founder": is_exec,
            "pain_indicators": pain_count,
        }
        logger.info(f"INTENT Inputs for {lead_name}: {result}")
        return result

