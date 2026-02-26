"""Intent Scorer - aggregates signals into intent/readiness scores."""
from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal


class IntentScorer:
    """
    Aggregates intelligence into scores:
    - Fit Score: How well does lead match ICP?
    - Readiness Score: Are they ready to buy?
    - Intent Score: Are they actively looking?
    - Composite Score: Overall priority
    """
    
    # Scoring weights
    WEIGHTS = {
        "fit": 0.30,
        "readiness": 0.35,
        "intent": 0.35,
    }
    
    # Intent signals and their scores
    INTENT_SIGNALS = {
        # Job postings (High intent)
        "hiring_related_roles": 0.25,
        "hiring_tech_roles": 0.15,
        
        # Company events (Medium-High intent)
        "funding_recent": 0.20,
        "new_executive": 0.15,
        "expansion": 0.15,
        
        # LinkedIn signals (Medium intent)
        "new_role_90d": 0.10,
        "posts_relevant_topics": 0.10,
        
        # Website signals (Low-Medium intent)
        "tech_stack_match": 0.10,
        "pain_indicators": 0.10,
    }
    
    def score(
        self,
        your_company_profile: Dict[str, Any],
        lead_intelligence: Dict[str, Any],
        linkedin_data: Optional[Dict[str, Any]] = None,
        google_triggers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate all scores for a lead.
        
        Returns:
            Dict with fit_score, readiness_score, intent_score, composite_score
        """
        
        fit_score = self._calculate_fit_score(your_company_profile, lead_intelligence)
        readiness_score = self._calculate_readiness_score(lead_intelligence, linkedin_data)
        intent_score = self._calculate_intent_score(
            lead_intelligence, 
            linkedin_data, 
            google_triggers
        )
        
        # Composite score
        composite = (
            fit_score * self.WEIGHTS["fit"] +
            readiness_score * self.WEIGHTS["readiness"] +
            intent_score * self.WEIGHTS["intent"]
        )
        
        return {
            "fit_score": round(fit_score, 2),
            "readiness_score": round(readiness_score, 2),
            "intent_score": round(intent_score, 2),
            "composite_score": round(composite, 2),
            "score_breakdown": {
                "fit": self._get_fit_breakdown(your_company_profile, lead_intelligence),
                "readiness": self._get_readiness_breakdown(lead_intelligence, linkedin_data),
                "intent": self._get_intent_breakdown(lead_intelligence, linkedin_data, google_triggers),
            },
            "scored_at": datetime.utcnow().isoformat(),
        }
    
    def _calculate_fit_score(
        self,
        your_profile: Dict[str, Any],
        lead_intel: Dict[str, Any],
    ) -> float:
        """Calculate ICP fit score (0-1)."""
        score = 0.0
        max_score = 1.0
        
        # Industry match
        your_industries = [i.lower() for i in your_profile.get("industries_served", [])]
        lead_industry = lead_intel.get("industry", "").lower()
        
        if lead_industry and any(ind in lead_industry or lead_industry in ind for ind in your_industries):
            score += 0.30
        elif lead_industry:
            score += 0.10  # Some industry info is better than none
        
        # Company size match (if we serve that segment)
        company_size = lead_intel.get("company_size_estimate", "")
        if company_size in ["medium", "enterprise"]:
            score += 0.25
        elif company_size == "small":
            score += 0.15
        
        # Pain indicators present
        pain_indicators = lead_intel.get("pain_indicators", [])
        if pain_indicators:
            # More pain = better fit
            pain_count = len(pain_indicators)
            score += min(0.25, pain_count * 0.08)
        
        # Tech stack alignment (if relevant)
        tech_stack = lead_intel.get("tech_stack_hints", [])
        if tech_stack:
            score += 0.10
        
        # GTM motion alignment
        gtm = lead_intel.get("gtm_motion", "")
        if gtm in ["enterprise", "hybrid"]:
            score += 0.10
        
        return min(score, max_score)
    
    def _calculate_readiness_score(
        self,
        lead_intel: Dict[str, Any],
        linkedin_data: Optional[Dict[str, Any]],
    ) -> float:
        """Calculate buying readiness score (0-1)."""
        score = 0.0
        
        # Buying signals from website
        buying_signals = lead_intel.get("buying_signals", [])
        if buying_signals:
            score += min(0.30, len(buying_signals) * 0.10)
        
        # Job signals (hiring for relevant roles)
        job_signals = lead_intel.get("job_signals", {})
        relevant_roles = job_signals.get("relevant_roles", [])
        if relevant_roles:
            score += min(0.25, len(relevant_roles) * 0.08)
        
        hiring_intensity = job_signals.get("hiring_intensity", "low")
        if hiring_intensity == "high":
            score += 0.15
        elif hiring_intensity == "medium":
            score += 0.08
        
        # LinkedIn: new role signals readiness
        if linkedin_data:
            job_change_days = linkedin_data.get("job_change_days")
            if job_change_days is not None:
                if job_change_days < 90:
                    score += 0.15  # New in role, setting priorities
                elif job_change_days < 180:
                    score += 0.10
            
            # Seniority (decision maker)
            seniority = linkedin_data.get("seniority", "")
            if seniority in ["senior", "executive"]:
                score += 0.15
            elif seniority == "mid":
                score += 0.05
        
        return min(score, 1.0)
    
    def _calculate_intent_score(
        self,
        lead_intel: Dict[str, Any],
        linkedin_data: Optional[Dict[str, Any]],
        triggers: Optional[List[Dict[str, Any]]],
    ) -> float:
        """Calculate active intent score (0-1).
        
        LinkedIn signals have been boosted to compensate for when
        Google Search triggers are not available.
        """
        score = 0.0
        
        # Google triggers are strong intent signals
        if triggers:
            for trigger in triggers:
                trigger_type = trigger.get("type", "").lower()
                confidence = trigger.get("confidence", 0.5)
                recency_days = trigger.get("recency_days")
                if recency_days is None:
                    recency_days = 999
                
                # Base score for trigger
                trigger_score = 0.0
                
                if "funding" in trigger_type:
                    trigger_score = 0.20
                elif "hiring" in trigger_type:
                    trigger_score = 0.15
                elif "new_exec" in trigger_type or "new cio" in trigger_type.lower():
                    trigger_score = 0.15
                elif "expansion" in trigger_type:
                    trigger_score = 0.12
                elif "product" in trigger_type:
                    trigger_score = 0.08
                else:
                    trigger_score = 0.05
                
                # Adjust for recency
                if recency_days <= 30:
                    trigger_score *= 1.2
                elif recency_days <= 90:
                    trigger_score *= 1.0
                else:
                    trigger_score *= 0.5
                
                # Adjust for confidence
                trigger_score *= confidence
                
                score += trigger_score
        
        # LinkedIn activity signals - BOOSTED for when Google is unavailable
        if linkedin_data:
            topics = linkedin_data.get("topics_30d", [])
            initiatives = linkedin_data.get("likely_initiatives", [])
            conversation_starters = linkedin_data.get("conversation_starters", [])
            seniority = linkedin_data.get("seniority", "").lower()
            
            # Posting about relevant topics (boosted: 0.10 each, max 0.30)
            if topics:
                score += min(0.30, len(topics) * 0.10)
            
            # Growth/tech initiatives (boosted: 0.10 each, max 0.30)
            if initiatives:
                score += min(0.30, len(initiatives) * 0.10)
            
            # Conversation starters indicate engagement (0.05 each, max 0.15)
            if conversation_starters:
                score += min(0.15, len(conversation_starters) * 0.05)
            
            # Decision maker seniority boosts intent signal
            if seniority in ["c-suite", "founder", "vp"]:
                score += 0.15
            elif seniority in ["director", "senior"]:
                score += 0.08
            
            # Recent job change = new priorities = high intent
            job_change_days = linkedin_data.get("job_change_days")
            if job_change_days is not None and job_change_days < 90:
                score += 0.15
        
        # Pain indicators also signal potential intent
        pain_indicators = lead_intel.get("pain_indicators", [])
        if pain_indicators:
            score += min(0.15, len(pain_indicators) * 0.05)
        
        return min(score, 1.0)
    
    def _get_fit_breakdown(self, your_profile: Dict, lead_intel: Dict) -> List[str]:
        """Get explanation of fit score components."""
        breakdown = []
        
        industry = lead_intel.get("industry")
        if industry:
            breakdown.append(f"Industry: {industry}")
        
        size = lead_intel.get("company_size_estimate")
        if size:
            breakdown.append(f"Size: {size}")
        
        pain_count = len(lead_intel.get("pain_indicators", []))
        if pain_count:
            breakdown.append(f"Pain indicators: {pain_count}")
        
        return breakdown
    
    def _get_readiness_breakdown(self, lead_intel: Dict, linkedin_data: Optional[Dict]) -> List[str]:
        """Get explanation of readiness score components."""
        breakdown = []
        
        signals = lead_intel.get("buying_signals", [])
        if signals:
            breakdown.append(f"Buying signals: {len(signals)}")
        
        if linkedin_data:
            seniority = linkedin_data.get("seniority")
            if seniority:
                breakdown.append(f"Seniority: {seniority}")
            
            job_days = linkedin_data.get("job_change_days")
            if job_days is not None and job_days < 180:
                breakdown.append(f"New in role: {job_days} days")
        
        return breakdown
    
    def _get_intent_breakdown(
        self, 
        lead_intel: Dict, 
        linkedin_data: Optional[Dict],
        triggers: Optional[List[Dict]]
    ) -> List[str]:
        """Get explanation of intent score components."""
        breakdown = []
        
        if triggers:
            for t in triggers[:3]:
                breakdown.append(f"Trigger: {t.get('type')} ({t.get('recency_days', '?')}d ago)")
        
        if linkedin_data:
            topics = linkedin_data.get("topics_30d", [])
            if topics:
                breakdown.append(f"LinkedIn topics: {', '.join(topics[:3])}")
        
        return breakdown
