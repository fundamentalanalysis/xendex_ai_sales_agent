"""Strategy Engine - determines outreach approach based on intelligence."""
from typing import Any, Dict, List, Optional
from enum import Enum
import structlog


logger = structlog.get_logger()


class EmailAngle(str, Enum):
    """Email approach/angle types."""
    TRIGGER_LED = "trigger-led"
    PROBLEM_HYPOTHESIS = "problem-hypothesis"
    CASE_STUDY = "case-study"
    QUICK_QUESTION = "quick-question"
    VALUE_INSIGHT = "value-insight"


class CTAType(str, Enum):
    """Call-to-action types."""
    CALL = "call"                    # "Can we chat for 15 min?"
    REPLY = "reply"                  # "Would love to hear your thoughts"
    REPLY_YES_NO = "reply_yes_no"    # "Worth a conversation? Y/N"
    RESOURCE = "resource"            # "Here's a guide that might help"
    MEETING_LINK = "meeting_link"    # "Here's my calendar link"


class Tone(str, Enum):
    """Email tone types."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    URGENT = "urgent"
    CONSULTATIVE = "consultative"


class StrategyEngine:
    """
    Determines the optimal outreach strategy based on:
    - Lead intelligence
    - Triggers found
    - LinkedIn data
    - Scores
    - Personalization mode
    
    Outputs:
    - Email angle
    - CTA type
    - Personalization depth
    - Sequence plan
    - Tone
    """
    
    def determine_strategy(
        self,
        lead_intelligence: Dict[str, Any],
        linkedin_data: Optional[Dict[str, Any]] = None,
        triggers: Optional[List[Dict[str, Any]]] = None,
        scores: Optional[Dict[str, Any]] = None,
        personalization_mode: str = "medium",
        risk_assessment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Determine the optimal outreach strategy.
        
        Args:
            lead_intelligence: Output from LeadIntelligenceAgent
            linkedin_data: Output from LinkedInAgent
            triggers: Output from GoogleResearchAgent
            scores: Output from IntentScorer
            personalization_mode: light/medium/deep
            risk_assessment: Output from RiskFilterAgent
            
        Returns:
            Complete strategy specification
        """
        logger.info("Determining strategy", personalization_mode=personalization_mode)
        
        # Determine best angle
        angle, angle_reason = self._select_angle(
            triggers=triggers,
            linkedin_data=linkedin_data,
            lead_intelligence=lead_intelligence,
        )
        
        # Determine CTA
        cta, cta_reason = self._select_cta(
            scores=scores,
            risk_assessment=risk_assessment,
            angle=angle,
        )
        
        # Determine tone
        tone = self._select_tone(
            linkedin_data=linkedin_data,
            lead_intelligence=lead_intelligence,
            risk_assessment=risk_assessment,
        )
        
        # Build pain hypothesis
        pain_hypothesis = self._build_pain_hypothesis(
            lead_intelligence=lead_intelligence,
            triggers=triggers,
            linkedin_data=linkedin_data,
        )
        
        # Determine sequence plan
        sequence = self._plan_sequence(
            angle=angle,
            scores=scores,
            risk_assessment=risk_assessment,
        )
        
        # Adjust for risk
        if risk_assessment and risk_assessment.get("action") == "delay":
            cta = CTAType.REPLY.value  # Softer CTA
            tone = Tone.CONSULTATIVE.value
        
        strategy = {
            "angle": angle,
            "angle_reason": angle_reason,
            "pain_hypothesis": pain_hypothesis,
            "cta": cta,
            "cta_reason": cta_reason,
            "tone": tone,
            "personalization_depth": personalization_mode,
            "sequence": sequence,
            "evidence_to_use": self._select_evidence(
                triggers=triggers,
                linkedin_data=linkedin_data,
                lead_intelligence=lead_intelligence,
                personalization_mode=personalization_mode,
            ),
        }
        
        return strategy
    
    def _select_angle(
        self,
        triggers: Optional[List[Dict[str, Any]]],
        linkedin_data: Optional[Dict[str, Any]],
        lead_intelligence: Dict[str, Any],
    ) -> tuple:
        """Select the best email angle."""
        
        # Priority 1: Strong, recent trigger
        if triggers:
            strong_triggers = [
                t for t in triggers 
                if t.get("confidence", 0) > 0.7 and t.get("recency_days", 999) < 60
            ]
            if strong_triggers:
                return (
                    EmailAngle.TRIGGER_LED.value,
                    f"Strong trigger: {strong_triggers[0].get('type', 'event')}"
                )
        
        # Priority 2: LinkedIn shows specific initiative
        if linkedin_data:
            initiatives = linkedin_data.get("likely_initiatives", [])
            topics = linkedin_data.get("topics_30d", [])
            
            if initiatives or topics:
                return (
                    EmailAngle.PROBLEM_HYPOTHESIS.value,
                    f"LinkedIn activity suggests: {(initiatives or topics)[0]}"
                )
        
        # Priority 3: Strong pain indicators
        pain_indicators = lead_intelligence.get("pain_indicators", [])
        if pain_indicators and len(pain_indicators) >= 2:
            return (
                EmailAngle.PROBLEM_HYPOTHESIS.value,
                "Multiple pain indicators detected"
            )
        
        # Priority 4: We have relevant case studies for their industry
        industry = lead_intelligence.get("industry", "")
        if industry:
            return (
                EmailAngle.CASE_STUDY.value,
                f"Industry match: {industry}"
            )
        
        # Default: Value insight
        return (
            EmailAngle.VALUE_INSIGHT.value,
            "Default approach - sharing value/insight"
        )
    
    def _select_cta(
        self,
        scores: Optional[Dict[str, Any]],
        risk_assessment: Optional[Dict[str, Any]],
        angle: str,
    ) -> tuple:
        """Select the appropriate CTA."""
        
        # High risk = softer CTA
        if risk_assessment and risk_assessment.get("risk_level") in ["medium", "high"]:
            return (
                CTAType.REPLY.value,
                "Softer CTA due to risk signals"
            )
        
        # High composite score = more direct CTA
        if scores:
            composite = scores.get("composite_score", 0)
            
            if composite >= 0.7:
                return (
                    CTAType.CALL.value,
                    f"High score ({composite}) warrants direct CTA"
                )
            elif composite >= 0.5:
                return (
                    CTAType.REPLY_YES_NO.value,
                    "Medium score - binary question CTA"
                )
        
        # Trigger-led = capitalize on timing
        if angle == EmailAngle.TRIGGER_LED.value:
            return (
                CTAType.REPLY_YES_NO.value,
                "Trigger-led angle works well with quick response ask"
            )
        
        # Case study = offer to share more
        if angle == EmailAngle.CASE_STUDY.value:
            return (
                CTAType.RESOURCE.value,
                "Case study angle - offer detailed content"
            )
        
        # Default
        return (
            CTAType.REPLY.value,
            "Default soft CTA"
        )
    
    def _select_tone(
        self,
        linkedin_data: Optional[Dict[str, Any]],
        lead_intelligence: Dict[str, Any],
        risk_assessment: Optional[Dict[str, Any]],
    ) -> str:
        """Select appropriate tone."""
        
        # Risk = more consultative
        if risk_assessment and risk_assessment.get("risk_level") == "high":
            return Tone.CONSULTATIVE.value
        
        # Executive = professional
        if linkedin_data:
            seniority = linkedin_data.get("seniority", "")
            if seniority == "executive":
                return Tone.PROFESSIONAL.value
        
        # Default
        return Tone.PROFESSIONAL.value
    
    def _build_pain_hypothesis(
        self,
        lead_intelligence: Dict[str, Any],
        triggers: Optional[List[Dict[str, Any]]],
        linkedin_data: Optional[Dict[str, Any]],
    ) -> str:
        """Build a pain hypothesis to use in outreach."""
        
        # From LinkedIn initiatives
        if linkedin_data:
            initiatives = linkedin_data.get("likely_initiatives", [])
            if initiatives:
                return f"Working on {initiatives[0]}"
        
        # From triggers
        if triggers:
            for trigger in triggers:
                if trigger.get("sales_implication"):
                    return trigger["sales_implication"]
        
        # From pain indicators
        pain_indicators = lead_intelligence.get("pain_indicators", [])
        if pain_indicators:
            first_pain = pain_indicators[0]
            if isinstance(first_pain, dict):
                return first_pain.get("indicator", "operational efficiency")
            return str(first_pain)
        
        # From industry common pains
        industry = lead_intelligence.get("industry", "")
        industry_pains = {
            "technology": "scaling engineering teams efficiently",
            "finance": "modernizing legacy systems",
            "healthcare": "compliance and data management",
            "retail": "digital transformation and customer experience",
            "manufacturing": "operational efficiency and automation",
        }
        
        for key, pain in industry_pains.items():
            if key.lower() in industry.lower():
                return pain
        
        return "improving operational efficiency"
    
    def _plan_sequence(
        self,
        angle: str,
        scores: Optional[Dict[str, Any]],
        risk_assessment: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Plan the email sequence."""
        
        # Base sequence
        sequence = {
            "touches": 3,
            "touch_delays": [3, 5],  # days between touches
            "t1_type": angle,
            "t2_type": "follow_up",
            "t3_type": "breakup",
        }
        
        # High score = can be more aggressive
        if scores and scores.get("composite_score", 0) >= 0.7:
            sequence["touch_delays"] = [2, 4]
        
        # High risk = slower sequence
        if risk_assessment and risk_assessment.get("risk_level") == "high":
            sequence["touch_delays"] = [5, 7]
            sequence["touches"] = 2
        
        return sequence
    
    def _select_evidence(
        self,
        triggers: Optional[List[Dict[str, Any]]],
        linkedin_data: Optional[Dict[str, Any]],
        lead_intelligence: Dict[str, Any],
        personalization_mode: str,
    ) -> Dict[str, Any]:
        """Select evidence to use based on personalization depth."""
        
        evidence = {
            "triggers": [],
            "linkedin_insights": {},
            "pain_indicators": [],
            "proof_points": [],
        }
        
        # Light: Just role + industry
        if personalization_mode == "light":
            return evidence
        
        # Medium: Add best trigger and one insight
        if personalization_mode in ["medium", "deep"]:
            if triggers:
                # Best trigger
                best_trigger = max(
                    triggers,
                    key=lambda t: (t.get("confidence", 0), -t.get("recency_days", 999))
                )
                evidence["triggers"].append(best_trigger)
            
            if linkedin_data:
                evidence["linkedin_insights"] = {
                    "topics": linkedin_data.get("topics_30d", [])[:2],
                    "initiatives": linkedin_data.get("likely_initiatives", [])[:2],
                }
        
        # Deep: Add multiple triggers, pain indicators, use proof points
        if personalization_mode == "deep":
            if triggers:
                evidence["triggers"] = triggers[:3]
            
            evidence["pain_indicators"] = lead_intelligence.get("pain_indicators", [])[:3]
            
            if linkedin_data:
                evidence["linkedin_insights"]["conversation_starters"] = \
                    linkedin_data.get("conversation_starters", [])
        
        return evidence
