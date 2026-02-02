"""Risk Filter Agent - detects negative signals and timing risks."""
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

from app.agents.base import BaseAgent


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskAction(str, Enum):
    SEND = "send"
    DELAY = "delay"
    SKIP = "skip"


# Risk signals to look for
NEGATIVE_SIGNALS = [
    {"pattern": "layoff", "risk": RiskLevel.HIGH, "action": RiskAction.DELAY},
    {"pattern": "laying off", "risk": RiskLevel.HIGH, "action": RiskAction.DELAY},
    {"pattern": "hiring freeze", "risk": RiskLevel.HIGH, "action": RiskAction.DELAY},
    {"pattern": "restructuring", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
    {"pattern": "bankruptcy", "risk": RiskLevel.HIGH, "action": RiskAction.SKIP},
    {"pattern": "acquired by", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
    {"pattern": "merger", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
    {"pattern": "controversy", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
    {"pattern": "lawsuit", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
    {"pattern": "data breach", "risk": RiskLevel.HIGH, "action": RiskAction.DELAY},
    {"pattern": "ceo departed", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
    {"pattern": "ceo resigned", "risk": RiskLevel.MEDIUM, "action": RiskAction.DELAY},
]


class RiskFilterAgent(BaseAgent):
    """
    Detects negative signals and timing risks:
    - Layoffs / hiring freeze
    - M&A / restructuring
    - Executive churn
    - Bad press / controversies
    - Competitor lock-in signals
    
    Decision: send / delay / skip
    """
    
    async def run(
        self,
        lead_intelligence: Dict[str, Any],
        google_triggers: Optional[List[Dict[str, Any]]] = None,
        linkedin_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assess risk for a lead.
        
        Args:
            lead_intelligence: Output from LeadIntelligenceAgent
            google_triggers: Output from GoogleResearchAgent
            linkedin_data: Output from LinkedInAgent
            
        Returns:
            Risk assessment with action recommendation
        """
        self._log_start()
        
        risks_found = []
        
        # Check Google triggers for negative signals
        if google_triggers:
            trigger_risks = self._check_trigger_risks(google_triggers)
            risks_found.extend(trigger_risks)
        
        # Check lead intelligence for pain indicators that might be risks
        if lead_intelligence:
            intel_risks = self._check_intelligence_risks(lead_intelligence)
            risks_found.extend(intel_risks)
        
        # Check LinkedIn for timing risks
        if linkedin_data:
            linkedin_risks = self._check_linkedin_risks(linkedin_data)
            risks_found.extend(linkedin_risks)
        
        # Determine overall risk level and action
        decision = self._make_decision(risks_found)
        
        result = {
            "success": True,
            "risks_found": risks_found,
            "risk_count": len(risks_found),
            "risk_level": decision["risk_level"],
            "action": decision["action"],
            "reason": decision["reason"],
            "assessed_at": datetime.utcnow().isoformat(),
        }
        
        self._log_complete(risk_level=decision["risk_level"], action=decision["action"])
        return result
    
    def _check_trigger_risks(self, triggers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check triggers for negative signals."""
        risks = []
        
        for trigger in triggers:
            summary = trigger.get("summary", "").lower()
            trigger_type = trigger.get("type", "").lower()
            
            # Check against negative signal patterns
            for signal in NEGATIVE_SIGNALS:
                if signal["pattern"] in summary or signal["pattern"] in trigger_type:
                    # Check recency - more recent = higher risk
                    recency_days = trigger.get("recency_days", 999)
                    
                    if recency_days <= 30:
                        risk_boost = "very recent"
                    elif recency_days <= 90:
                        risk_boost = "recent"
                    else:
                        risk_boost = "older"
                    
                    risks.append({
                        "signal": signal["pattern"],
                        "source": "google_trigger",
                        "evidence": trigger.get("summary", ""),
                        "recency": risk_boost,
                        "recency_days": recency_days,
                        "risk_level": signal["risk"].value,
                        "suggested_action": signal["action"].value,
                    })
        
        return risks
    
    def _check_intelligence_risks(self, intel: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check lead intelligence for risk signals."""
        risks = []
        
        # Check pain indicators for negative signals
        pain_indicators = intel.get("pain_indicators", [])
        for indicator in pain_indicators:
            text = indicator.get("indicator", "").lower() if isinstance(indicator, dict) else str(indicator).lower()
            
            for signal in NEGATIVE_SIGNALS:
                if signal["pattern"] in text:
                    risks.append({
                        "signal": signal["pattern"],
                        "source": "lead_intelligence",
                        "evidence": text,
                        "risk_level": signal["risk"].value,
                        "suggested_action": signal["action"].value,
                    })
        
        return risks
    
    def _check_linkedin_risks(self, linkedin_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check LinkedIn data for timing risks."""
        risks = []
        
        # Very new job = might not have budget authority yet
        job_change_days = linkedin_data.get("job_change_days")
        if job_change_days is not None and job_change_days < 30:
            risks.append({
                "signal": "very_new_role",
                "source": "linkedin",
                "evidence": f"Started role {job_change_days} days ago",
                "risk_level": RiskLevel.LOW.value,
                "suggested_action": RiskAction.SEND.value,  # Actually a mild positive
                "note": "New in role - may be setting priorities",
            })
        
        # Check topics for negative signals
        topics = linkedin_data.get("topics_30d", [])
        for topic in topics:
            topic_lower = topic.lower()
            for signal in NEGATIVE_SIGNALS:
                if signal["pattern"] in topic_lower:
                    risks.append({
                        "signal": signal["pattern"],
                        "source": "linkedin_activity",
                        "evidence": topic,
                        "risk_level": signal["risk"].value,
                        "suggested_action": signal["action"].value,
                    })
        
        return risks
    
    def _make_decision(self, risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Make final risk decision based on all risks found."""
        
        if not risks:
            return {
                "risk_level": RiskLevel.LOW.value,
                "action": RiskAction.SEND.value,
                "reason": "No risk signals detected",
            }
        
        # Count risks by level
        high_risks = [r for r in risks if r["risk_level"] == RiskLevel.HIGH.value]
        medium_risks = [r for r in risks if r["risk_level"] == RiskLevel.MEDIUM.value]
        
        # Decision logic
        if high_risks:
            # Check if any suggest skip
            skip_risks = [r for r in high_risks if r.get("suggested_action") == RiskAction.SKIP.value]
            if skip_risks:
                return {
                    "risk_level": RiskLevel.HIGH.value,
                    "action": RiskAction.SKIP.value,
                    "reason": skip_risks[0].get("evidence", "High risk detected"),
                }
            
            # Recent high risks = delay
            recent_high = [r for r in high_risks if r.get("recency_days", 999) <= 60]
            if recent_high:
                return {
                    "risk_level": RiskLevel.HIGH.value,
                    "action": RiskAction.DELAY.value,
                    "reason": recent_high[0].get("evidence", "Recent high risk event"),
                }
        
        if medium_risks:
            # Multiple medium risks = delay
            if len(medium_risks) >= 2:
                return {
                    "risk_level": RiskLevel.MEDIUM.value,
                    "action": RiskAction.DELAY.value,
                    "reason": f"Multiple risk signals: {', '.join(r['signal'] for r in medium_risks[:3])}",
                }
        
        # Default: proceed with caution
        return {
            "risk_level": RiskLevel.LOW.value if not medium_risks else RiskLevel.MEDIUM.value,
            "action": RiskAction.SEND.value,
            "reason": "Acceptable risk level",
        }
