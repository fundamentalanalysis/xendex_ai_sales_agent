"""Personalization control based on mode (light/medium/deep)."""
from typing import Any, Dict, List, Optional


class PersonalizationController:
    """
    Controls personalization depth based on mode setting.
    
    Modes:
    - Light: industry + role only
    - Medium: + 1 trigger/news
    - Deep: + trigger + LinkedIn priority + specific pain hypothesis
    """
    
    # What to include at each level
    LEVELS = {
        "light": {
            "include_industry": True,
            "include_role": True,
            "include_company_name": True,
            "include_trigger": False,
            "include_linkedin": False,
            "include_pain_hypothesis": False,
            "include_proof_points": False,
            "max_personalization_elements": 2,
        },
        "medium": {
            "include_industry": True,
            "include_role": True,
            "include_company_name": True,
            "include_trigger": True,
            "include_linkedin": True,
            "include_pain_hypothesis": True,
            "include_proof_points": False,
            "max_personalization_elements": 4,
            "max_triggers": 1,
            "max_linkedin_topics": 1,
        },
        "deep": {
            "include_industry": True,
            "include_role": True,
            "include_company_name": True,
            "include_trigger": True,
            "include_linkedin": True,
            "include_pain_hypothesis": True,
            "include_proof_points": True,
            "max_personalization_elements": 8,
            "max_triggers": 3,
            "max_linkedin_topics": 3,
            "include_conversation_starters": True,
        },
    }
    
    def get_personalization_context(
        self,
        mode: str,
        lead_data: Dict[str, Any],
        intelligence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get personalization context based on mode.
        
        Args:
            mode: light, medium, or deep
            lead_data: Basic lead info
            intelligence: Normalized lead intelligence
            
        Returns:
            Filtered context for email generation
        """
        config = self.LEVELS.get(mode, self.LEVELS["medium"])
        
        context = {
            "mode": mode,
            "elements_used": [],
        }
        
        # Always included
        if config["include_company_name"]:
            context["company_name"] = lead_data.get("company_name", "")
            context["elements_used"].append("company_name")
        
        if config["include_role"]:
            context["role"] = intelligence.get("contact", {}).get("role", "")
            if context["role"]:
                context["elements_used"].append("role")
        
        if config["include_industry"]:
            context["industry"] = intelligence.get("lead_company", {}).get("industry", "")
            if context["industry"]:
                context["elements_used"].append("industry")
        
        # Medium+ features
        if config.get("include_trigger"):
            triggers = intelligence.get("triggers", [])
            max_triggers = config.get("max_triggers", 1)
            context["triggers"] = triggers[:max_triggers]
            if context["triggers"]:
                context["elements_used"].append("trigger")
        
        if config.get("include_linkedin"):
            contact = intelligence.get("contact", {})
            max_topics = config.get("max_linkedin_topics", 1)
            
            context["linkedin"] = {
                "topics": contact.get("topics_30d", [])[:max_topics],
                "initiatives": contact.get("likely_initiatives", [])[:max_topics],
            }
            
            if context["linkedin"]["topics"] or context["linkedin"]["initiatives"]:
                context["elements_used"].append("linkedin_activity")
        
        if config.get("include_pain_hypothesis"):
            hypotheses = intelligence.get("pain_hypotheses", [])
            context["pain_hypotheses"] = hypotheses[:1]  # Just top one for medium
            if context["pain_hypotheses"]:
                context["elements_used"].append("pain_hypothesis")
        
        # Deep features
        if config.get("include_proof_points"):
            your_company = intelligence.get("your_company", {})
            industry = context.get("industry", "").lower()
            
            # Find relevant proof points
            proof_points = your_company.get("proof_points", [])
            relevant = [
                pp for pp in proof_points
                if industry in (pp.get("industry", "") or "").lower()
            ]
            
            context["proof_points"] = relevant[:2] if relevant else proof_points[:1]
            if context["proof_points"]:
                context["elements_used"].append("proof_point")
        
        if config.get("include_conversation_starters"):
            starters = intelligence.get("contact", {}).get("conversation_starters", [])
            context["conversation_starters"] = starters[:2]
            if context["conversation_starters"]:
                context["elements_used"].append("conversation_starter")
        
        # Pain hypotheses for deep mode
        if mode == "deep" and config.get("include_pain_hypothesis"):
            context["pain_hypotheses"] = intelligence.get("pain_hypotheses", [])[:3]
        
        return context
    
    def filter_for_template(
        self,
        mode: str,
        template_vars: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Filter template variables based on mode.
        
        Ensures we don't over-personalize in light mode.
        """
        config = self.LEVELS.get(mode, self.LEVELS["medium"])
        max_elements = config["max_personalization_elements"]
        
        # Count personalization elements used
        element_count = 0
        filtered = {}
        
        # Priority order for inclusion
        priority_keys = [
            "first_name",
            "company_name",
            "role",
            "industry",
            "trigger_reference",
            "linkedin_topic",
            "pain_hypothesis",
            "proof_point",
        ]
        
        for key in priority_keys:
            if key in template_vars and template_vars[key]:
                if element_count < max_elements:
                    filtered[key] = template_vars[key]
                    element_count += 1
                else:
                    # Replace with generic
                    filtered[key] = self._get_generic(key)
        
        # Copy any remaining keys
        for key, value in template_vars.items():
            if key not in filtered:
                filtered[key] = value
        
        return filtered
    
    def _get_generic(self, key: str) -> str:
        """Get generic replacement for personalization element."""
        generics = {
            "trigger_reference": "recent developments",
            "linkedin_topic": "your focus areas",
            "pain_hypothesis": "operational efficiency",
            "proof_point": "our track record",
        }
        return generics.get(key, "")
    
    def validate_personalization(
        self,
        draft_body: str,
        mode: str,
        expected_elements: List[str],
    ) -> Dict[str, Any]:
        """
        Validate that personalization matches the mode.
        
        Returns:
            Validation result with any issues found
        """
        config = self.LEVELS.get(mode, self.LEVELS["medium"])
        max_elements = config["max_personalization_elements"]
        
        issues = []
        
        # Check element count
        if len(expected_elements) > max_elements:
            issues.append(
                f"Too many personalization elements ({len(expected_elements)} > {max_elements})"
            )
        
        # Check for over-personalization in light mode
        if mode == "light":
            forbidden = ["trigger", "linkedin", "pain_hypothesis"]
            for element in expected_elements:
                if any(f in element.lower() for f in forbidden):
                    issues.append(f"Element '{element}' not allowed in light mode")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "mode": mode,
            "elements_used": len(expected_elements),
            "max_allowed": max_elements,
        }
