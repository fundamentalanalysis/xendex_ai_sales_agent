"""LinkedIn Intelligence Pydantic models for validation and type safety."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class CoreIdentity(BaseModel):
    """Core identity information from LinkedIn profile."""
    full_name: Optional[str] = None
    current_title: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None


class AuthoritySignals(BaseModel):
    """Authority and decision-making signals."""
    seniority_level: str = Field(default="unknown", description="junior|mid|senior|director|vp|c-suite|founder")
    decision_maker: bool = False
    budget_authority: str = Field(default="none", description="none|small|medium|large|enterprise")
    years_in_current_role: Optional[str] = None
    team_responsibility: Optional[str] = None
    can_authorize_purchase: bool = False
    reasoning: Optional[str] = None
    
    @field_validator("seniority_level")
    @classmethod
    def validate_seniority(cls, v: str) -> str:
        valid = ["junior", "mid", "senior", "director", "vp", "c-suite", "founder", "unknown"]
        return v.lower() if v.lower() in valid else "unknown"
    
    @field_validator("budget_authority")
    @classmethod
    def validate_budget(cls, v: str) -> str:
        valid = ["none", "small", "medium", "large", "enterprise"]
        return v.lower() if v.lower() in valid else "none"


class PersonalizationSignals(BaseModel):
    """Signals for email personalization."""
    recent_topics: List[str] = Field(default_factory=list)
    recent_post_summary: Optional[str] = None
    featured_content: Optional[str] = None
    keywords_used: List[str] = Field(default_factory=list)
    conversation_starters: List[str] = Field(default_factory=list)


class CompanyContext(BaseModel):
    """Company context and growth signals."""
    company_name: Optional[str] = None
    company_size_estimate: Optional[str] = None
    growth_phase: str = Field(default="unknown", description="startup|scaling|mature|unknown")
    hiring_signal: bool = False
    recent_news: List[str] = Field(default_factory=list)


class BuyingIntentSignals(BaseModel):
    """Buying intent and pain indicators."""
    intent_keywords: List[str] = Field(default_factory=list)
    technology_mentions: List[str] = Field(default_factory=list)
    pain_indicators: List[str] = Field(default_factory=list)
    growth_indicators: List[str] = Field(default_factory=list)
    hiring_indicators: List[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Categorized skills."""
    technical: List[str] = Field(default_factory=list)
    business: List[str] = Field(default_factory=list)
    leadership: List[str] = Field(default_factory=list)


class LeadScore(BaseModel):
    """Lead scoring with confidence."""
    score: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    
    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(0, min(100, v))


class EmailAngle(BaseModel):
    """Email angle classification."""
    primary: Optional[str] = None
    secondary: Optional[str] = None
    reasoning: Optional[str] = None


class OpeningLine(BaseModel):
    """Generated opening lines for cold emails."""
    line: Optional[str] = None
    alternative: Optional[str] = None


class LinkedInIntelligence(BaseModel):
    """Complete LinkedIn intelligence output - validated and typed."""
    
    # Source metadata
    success: bool = True
    source: str = "unknown"
    linkedin_url: Optional[str] = None
    analyzed_at: Optional[str] = None
    
    # Core data
    core_identity: CoreIdentity = Field(default_factory=CoreIdentity)
    authority_signals: AuthoritySignals = Field(default_factory=AuthoritySignals)
    personalization_signals: PersonalizationSignals = Field(default_factory=PersonalizationSignals)
    company_context: CompanyContext = Field(default_factory=CompanyContext)
    buying_intent_signals: BuyingIntentSignals = Field(default_factory=BuyingIntentSignals)
    skills: Skills = Field(default_factory=Skills)
    
    # Output
    cold_email_hooks: List[str] = Field(default_factory=list, max_length=5)
    lead_score: LeadScore = Field(default_factory=LeadScore)
    email_angle: EmailAngle = Field(default_factory=EmailAngle)
    opening_line: OpeningLine = Field(default_factory=OpeningLine)
    sales_priority: str = Field(default="low", description="low|medium|high|critical")
    
    # Raw data (optional)
    raw_data: Optional[Dict[str, Any]] = None
    
    @field_validator("sales_priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid = ["low", "medium", "high", "critical"]
        return v.lower() if v.lower() in valid else "low"
    
    @classmethod
    def from_llm_response(cls, response: Dict[str, Any], **kwargs) -> "LinkedInIntelligence":
        """Create from LLM response with safe defaults for missing fields."""
        return cls(
            core_identity=CoreIdentity(**response.get("core_identity", {})),
            authority_signals=AuthoritySignals(**response.get("authority_signals", {})),
            personalization_signals=PersonalizationSignals(**response.get("personalization_signals", {})),
            company_context=CompanyContext(**response.get("company_context", {})),
            buying_intent_signals=BuyingIntentSignals(**response.get("buying_intent_signals", {})),
            skills=Skills(**response.get("skills", {})),
            cold_email_hooks=response.get("cold_email_hooks", [])[:5],
            lead_score=LeadScore(**response.get("lead_score", {})),
            email_angle=EmailAngle(**response.get("email_angle", {})),
            opening_line=OpeningLine(**response.get("opening_line", {})) if isinstance(response.get("opening_line"), dict) else OpeningLine(line=response.get("opening_line")),
            sales_priority=response.get("sales_priority", "low"),
            **kwargs
        )
