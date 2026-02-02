"""Normalizer - builds Lead Intelligence Profile from agent outputs."""
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog

from app.agents.intent_scorer import IntentScorer

logger = structlog.get_logger()


class Normalizer:
    """
    Aggregates outputs from multiple agents into a single
    normalized Lead Intelligence Profile.
    
    Inputs:
    - Website Analyzer output (your company)
    - Lead Intelligence Agent output
    - LinkedIn Agent output
    - Google Research Agent output
    - Risk Filter output
    
    Output:
    - Unified LeadIntelligenceProfile with computed scores
    """
    
    def __init__(self):
        self.intent_scorer = IntentScorer()
    
    def normalize(
        self,
        your_company: Dict[str, Any],
        lead_company: Dict[str, Any],
        linkedin_data: Optional[Dict[str, Any]] = None,
        google_triggers: Optional[List[Dict[str, Any]]] = None,
        risk_assessment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build normalized Lead Intelligence Profile.
        
        Returns:
            Unified profile with all intelligence and scores
        """
        logger.info("Normalizing lead intelligence")
        
        # Compute scores
        scores = self.intent_scorer.score(
            your_company_profile=your_company,
            lead_intelligence=lead_company,
            linkedin_data=linkedin_data,
            google_triggers=google_triggers,
        )
        
        # Build normalized profile
        profile = {
            # Your company context
            "your_company": {
                "services": your_company.get("services", []),
                "proof_points": your_company.get("proof_points", []),
                "positioning": your_company.get("positioning", ""),
                "industries_served": your_company.get("industries_served", []),
            },
            
            # Lead company intelligence
            "lead_company": {
                "overview": lead_company.get("company_overview", ""),
                "industry": lead_company.get("industry", ""),
                "offerings": lead_company.get("offerings", []),
                "size_estimate": lead_company.get("company_size_estimate", ""),
                "gtm_motion": lead_company.get("gtm_motion", ""),
                "tech_stack": lead_company.get("tech_stack_hints", []),
                "pain_indicators": lead_company.get("pain_indicators", []),
                "buying_signals": lead_company.get("buying_signals", []),
                "job_signals": lead_company.get("job_signals", {}),
            },
            
            # LinkedIn intelligence
            "contact": {
                "role": (linkedin_data or {}).get("role"),
                "seniority": (linkedin_data or {}).get("seniority"),
                "company": (linkedin_data or {}).get("company"),
                "job_change_days": (linkedin_data or {}).get("job_change_days"),
                "topics_30d": (linkedin_data or {}).get("topics_30d", []),
                "likely_initiatives": (linkedin_data or {}).get("likely_initiatives", []),
                "conversation_starters": (linkedin_data or {}).get("conversation_starters", []),
            },
            
            # Google triggers
            "triggers": self._normalize_triggers(google_triggers),
            
            # Risk assessment
            "risk": {
                "level": (risk_assessment or {}).get("risk_level", "low"),
                "action": (risk_assessment or {}).get("action", "send"),
                "reason": (risk_assessment or {}).get("reason"),
                "risks_found": (risk_assessment or {}).get("risks_found", []),
            },
            
            # Scores
            "scores": {
                "fit_score": scores.get("fit_score"),
                "readiness_score": scores.get("readiness_score"),
                "intent_score": scores.get("intent_score"),
                "composite_score": scores.get("composite_score"),
                "score_breakdown": scores.get("score_breakdown", {}),
            },
            
            # Computed pain hypotheses
            "pain_hypotheses": self._build_pain_hypotheses(
                lead_company=lead_company,
                linkedin_data=linkedin_data,
                triggers=google_triggers,
            ),
            
            # Best angle recommendation
            "recommended_angle": self._recommend_angle(
                triggers=google_triggers,
                linkedin_data=linkedin_data,
                lead_company=lead_company,
            ),
            
            # Metadata
            "normalized_at": datetime.utcnow().isoformat(),
        }
        
        return profile
    
    def _normalize_triggers(
        self, 
        triggers: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Normalize and rank triggers."""
        if not triggers:
            return []
        
        # Ensure consistent structure
        normalized = []
        for trigger in triggers:
            normalized.append({
                "type": trigger.get("type", "unknown"),
                "summary": trigger.get("summary", ""),
                "recency_days": trigger.get("recency_days"),
                "confidence": trigger.get("confidence", 0.5),
                "evidence_url": trigger.get("evidence_url"),
                "sales_implication": trigger.get("sales_implication"),
            })
        
        # Sort by confidence and recency
        return sorted(
            normalized,
            key=lambda t: (t["confidence"], -(t.get("recency_days") or 999)),
            reverse=True,
        )
    
    def _build_pain_hypotheses(
        self,
        lead_company: Dict[str, Any],
        linkedin_data: Optional[Dict[str, Any]],
        triggers: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Build ranked pain hypotheses from evidence."""
        
        hypotheses = []
        
        # From pain indicators
        for indicator in lead_company.get("pain_indicators", []):
            text = indicator.get("indicator", indicator) if isinstance(indicator, dict) else str(indicator)
            evidence = indicator.get("evidence", "") if isinstance(indicator, dict) else ""
            
            hypotheses.append({
                "hypothesis": text,
                "source": "website_analysis",
                "confidence": 0.6,
                "evidence": evidence,
            })
        
        # From LinkedIn initiatives
        if linkedin_data:
            for initiative in linkedin_data.get("likely_initiatives", []):
                hypotheses.append({
                    "hypothesis": f"Working on {initiative}",
                    "source": "linkedin_activity",
                    "confidence": 0.7,
                    "evidence": f"LinkedIn activity indicates focus on {initiative}",
                })
        
        # From triggers
        if triggers:
            for trigger in triggers:
                if trigger.get("sales_implication"):
                    hypotheses.append({
                        "hypothesis": trigger["sales_implication"],
                        "source": "google_trigger",
                        "confidence": trigger.get("confidence", 0.5),
                        "evidence": trigger.get("summary"),
                    })
        
        # Deduplicate and rank
        seen = set()
        unique = []
        for h in hypotheses:
            key = h["hypothesis"].lower()[:50]
            if key not in seen:
                seen.add(key)
                unique.append(h)
        
        return sorted(unique, key=lambda h: h["confidence"], reverse=True)[:5]
    
    def _recommend_angle(
        self,
        triggers: Optional[List[Dict[str, Any]]],
        linkedin_data: Optional[Dict[str, Any]],
        lead_company: Dict[str, Any],
    ) -> str:
        """Recommend best outreach angle."""
        
        # Strong trigger = trigger-led
        if triggers:
            high_conf = [t for t in triggers if t.get("confidence", 0) > 0.7]
            recent = [t for t in triggers if (t.get("recency_days") or 999) < 60]
            if high_conf and recent:
                return "trigger-led"
        
        # LinkedIn activity = problem-hypothesis
        if linkedin_data and linkedin_data.get("likely_initiatives"):
            return "problem-hypothesis"
        
        # Industry match = case-study
        if lead_company.get("industry"):
            return "case-study"
        
        return "value-insight"
