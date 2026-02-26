"""Draft Generator - generates email drafts using LLM with guardrails."""
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog

from app.integrations.openai_client import OpenAIClient
from app.engine.strategy import StrategyEngine

logger = structlog.get_logger()


# Email templates for different angles
TEMPLATES = {
    "trigger-led": """Subject: {trigger_reference}

Hi {first_name},

I noticed {trigger_detail}. {insight_about_trigger}

We've helped companies like {similar_company} with {relevant_solution}.

{cta}

Best,
{signature}""",

    "problem-hypothesis": """Subject: Quick thought on {pain_area}

Hi {first_name},

Many {persona_type}s at {company_type} companies tell us {common_pain}.

{how_we_help}

{proof_point}

{cta}

Best,
{signature}""",

    "case-study": """Subject: How {case_study_company} achieved {outcome}

Hi {first_name},

{case_study_company} in {industry} was facing {similar_challenge}.

After working with us, they {result_achieved}.

Given {company}'s focus on {their_focus}, thought this might resonate.

{cta}

Best,
{signature}""",

    "quick-question": """Subject: Quick question, {first_name}

Hi {first_name},

{question_based_on_research}

{brief_context_why_asking}

{cta}

Best,
{signature}""",

    "value-insight": """Subject: {insight_headline}

Hi {first_name},

{insight_opening}

{why_this_matters_to_them}

{brief_about_us}

{cta}

Best,
{signature}""",

    # Follow-up templates
    "follow_up": """Subject: Re: {original_subject}

Hi {first_name},

Just circling back on my note from {days_ago} days ago.

{brief_reminder}

{new_angle_or_value}

{cta}

Best,
{signature}""",

    "breakup": """Subject: Should I close your file?

Hi {first_name},

I've reached out a couple of times about {topic}.

If {pain_hypothesis} isn't a priority right now, no worries at all.

If things change, feel free to reach out. Happy to help when the timing is right.

Best,
{signature}""",
}


# Guardrails for email generation
GUARDRAILS = """
CRITICAL RULES (NEVER VIOLATE):
1. Base emails ONLY on actual facts from provided intelligence. No assumptions.
2. DO NOT invent case studies, metrics, or company names.
3. DO NOT assume problems the lead hasn't indicated. Avoid "I work with teams navigating similar expansions" unless it's a verified fact.
4. DO NOT use pushy language like "Would you be open to a quick chat?". Instead use highly consultative, polite, and exploratory CTAs such as "I was wondering if it might be useful to connect for a brief 15-minute conversation next week to exchange perspectives... I’d be happy to work around your availability."
5. DO NOT apologize for outreach or use negative framing (e.g. NEVER say "I apologize for the interruption" or "If you are too busy").
6. Keep total length under 180 words for the body.
7. ALWAYS provide a polite, low-pressure soft out like "If now isn’t a good time, no worries at all—please feel free to reach out if it makes sense in the future."
8. ALWAYS be truthful, structured, and use a consultative peer-to-peer tone.

PROFESSIONAL STRUCTURE EXPECTATION:
- GREETING: Professional opening.
- CONTEXT: What we observed from research, phrased conversationally (e.g., "I recently came across... It was interesting to see how this aligns with...").
- INSIGHT: Share a generalized industry observation (e.g., "From conversations with other teams... I’ve noticed a growing focus on...").
- CTA: Polite, exploratory invitation to connect to exchange perspectives (e.g. "I was wondering if it might be useful to connect...").
- SOFT_OUT: Respectful acknowledgment if not interested (NO APOLOGIES).
- SOFT_OUT: Respectful acknowledgment if not interested (NO APOLOGIES).
- CLOSING: Professional signature.

PERSONALIZATION RULES:
- Lead with context observed from data, not assumptions.
- Provide real problem statements based on triggers.
"""


class DraftGenerator:
    """
    Generates email drafts with:
    - Multiple subject options
    - Personalization based on strategy
    - Guardrails against hallucination
    - Template guidance
    """
    
    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        self.openai = openai_client or OpenAIClient()
        self.strategy_engine = StrategyEngine()
    
    async def generate_draft(
        self,
        lead_data: Dict[str, Any],
        intelligence: Dict[str, Any],
        your_company: Dict[str, Any],
        strategy: Optional[Dict[str, Any]] = None,
        touch_number: int = 1,
        subject_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Generate an email draft for a lead.
        
        Args:
            lead_data: Basic lead info (name, email, company, role)
            intelligence: LeadIntelligence data
            your_company: Your company profile
            strategy: Pre-computed strategy (or will be computed)
            touch_number: Which touch in the sequence (1, 2, or 3)
            subject_count: Number of subject options to generate
            
        Returns:
            Draft with subject options and body
        """
        logger.info(
            "Generating draft",
            lead_company=lead_data.get("company_name"),
            touch=touch_number,
        )
        
        # Get or compute strategy
        if not strategy:
            strategy = self.strategy_engine.determine_strategy(
                lead_intelligence=intelligence,
                personalization_mode=lead_data.get("personalization_mode", "medium"),
            )
        
        # Determine template
        if touch_number == 1:
            template_type = strategy.get("angle", "value-insight")
        elif touch_number == 2:
            template_type = "follow_up"
        else:
            template_type = "breakup"
        
        template = TEMPLATES.get(template_type, TEMPLATES["value-insight"])
        
        # Build context for LLM
        context = self._build_generation_context(
            lead_data=lead_data,
            intelligence=intelligence,
            your_company=your_company,
            strategy=strategy,
            touch_number=touch_number,
            template=template,
        )
        
        # Generate with LLM
        draft = await self._generate_with_llm(
            context=context,
            template_type=template_type,
            subject_count=subject_count,
        )
        
        # Post-process and validate
        draft = self._validate_draft(draft, strategy)
        
        # Add metadata
        draft["touch_number"] = touch_number
        draft["strategy"] = strategy
        draft["evidence"] = strategy.get("evidence_to_use", {})
        draft["personalization_mode"] = strategy.get("personalization_depth", "medium")
        draft["generated_at"] = datetime.utcnow().isoformat()
        
        return draft
    
    def _build_generation_context(
        self,
        lead_data: Dict[str, Any],
        intelligence: Dict[str, Any],
        your_company: Dict[str, Any],
        strategy: Dict[str, Any],
        touch_number: int,
        template: str,
    ) -> Dict[str, Any]:
        """Build context for LLM generation."""
        
        linkedin = intelligence.get("linkedin_data", {})
        triggers = intelligence.get("triggers", [])
        
        return {
            # Lead info
            "first_name": lead_data.get("first_name", "there"),
            "last_name": lead_data.get("last_name", ""),
            "company": lead_data.get("company_name", "your company"),
            "role": linkedin.get("role") or lead_data.get("persona", ""),
            "industry": intelligence.get("industry", ""),
            
            # Strategy
            "angle": strategy.get("angle"),
            "pain_hypothesis": strategy.get("pain_hypothesis"),
            "cta": strategy.get("cta"),
            "tone": strategy.get("tone"),
            "personalization_mode": strategy.get("personalization_depth", "medium"),
            
            # Evidence
            "evidence": strategy.get("evidence_to_use", {}),
            "triggers": triggers[:2] if triggers else [],
            "linkedin_topics": linkedin.get("topics_30d", [])[:3],
            "linkedin_initiatives": linkedin.get("likely_initiatives", [])[:2],
            
            # Your company
            "your_services": your_company.get("positioning", "we help companies improve"),
            "your_positioning": your_company.get("positioning", ""),
            "proof_points": your_company.get("proof_points", [])[:2],
            
            # Template
            "template": template,
            "template_type": strategy.get("angle"),
            "touch_number": touch_number,
        }
    
    async def _generate_with_llm(
        self,
        context: Dict[str, Any],
        template_type: str,
        subject_count: int,
    ) -> Dict[str, Any]:
        """Generate email using LLM."""
        
        if template_type == "follow_up":
            prompt = f"""You are crafting a polite, professional follow-up email to a prospect who hasn't replied to your first message.
The goal is to gently bring the conversation back to the top of their inbox by adding value, not just "checking in".

{GUARDRAILS}

## RECIPIENT PROFILE
- Name: {context['first_name']} {context['last_name']}
- Role: {context['role']}
- Company: {context['company']}

## CONTEXT
- This is a follow-up to a previous email about: {context['pain_hypothesis']}
- Strategy Angle: {context['angle']}

## NEW VALUE TO ADD:
- Insight: {context.get('linkedin_topics', [])}
- Proof Point: {context.get('proof_points', [])}
- Trigger: {context.get('triggers', [])}

## YOUR TASK
Create a COMPLETELY NEW SHORT follow-up email (Touch 2) that:
1. Is completely freshly written. Do NOT reuse previous wording. Change angle, tone, structure, and phrasing.
2. Is significantly shorter than the first email (aim for < 80 words)
3. Does NOT just say "did you see my last email?"
4. PIVOTS to a new specific benefit or proof point
4. Respects their time
5. Ends with a simpler, lower-friction call to action (e.g. "Is this relevant?" or "Any interest?")

## OUTPUT FORMAT (JSON):
{{
    "subject_options": [
        "Re: [Previous Topic]",
        "Subject 2 - different angle/value prop",
        "Subject 3 - short question"
    ],
    "body": "The full email body - under 80 words. Direct and valuable.",
    "personalization_elements": ["List elements used"],
    "cta_used": "The exact CTA phrase you used"
}}

Make it feel like a human checking in, not a robot nagging."""
        
        else:
            prompt = f"""You are crafting a B2B cold email that will stand out in a busy inbox. The goal is to create a genuine, personalized message that opens doors—not a generic sales pitch.

{GUARDRAILS}

## RECIPIENT PROFILE
- Name: {context['first_name']} {context['last_name']}
- Role: {context['role']}
- Company: {context['company']}
- Industry: {context['industry']}

## INTELLIGENCE (use to personalize)
- Recent Triggers: {context.get('triggers', [])}
- LinkedIn Topics: {context.get('linkedin_topics', [])}
- Likely Initiatives: {context.get('linkedin_initiatives', [])}
- Pain Hypothesis: {context['pain_hypothesis']}

## YOUR COMPANY
- Positioning: {context['your_positioning']}
- Proof Points: {context.get('proof_points', [])}

## STRATEGY
- Approach: {context['angle']}
- Tone: {context['tone']} (be conversational, not corporate)
- CTA Type: {context['cta']}
- Personalization Level: {context['personalization_mode']}

## TEMPLATE INSPIRATION (adapt, don't copy verbatim):
{context['template']}

## YOUR TASK
Create a COMPLETELY NEW cold email that strictly follows the PROFESSIONAL STRUCTURE defined in the Guardrails.
Do not reuse previous wording. Change angle, tone, structure, and subject line to ensure this feels like a fresh variation.
1. Opens with a personalized context hook based on REAL data above. Use phrases like "I recently came across... It was interesting to see how this aligns with...".
2. Share a peer-to-peer industry observation (e.g., "From conversations with other teams... I’ve noticed a growing focus on...").
3. Uses a highly consultative, polite CTA (e.g., "I was wondering if it might be useful to connect for a brief 15-minute conversation next week to exchange perspectives... I’d be happy to work around your availability.").
4. Includes a low-pressure Soft Out (e.g., "If now isn’t a good time, no worries at all—please feel free to reach out if it makes sense in the future.").
5. Feels like it was written by a polite, professional, consultative human exchanging perspectives.
6. Uses proper formatting with explicit section components in mind and clear \n\n breaks between paragraphs.

## OUTPUT FORMAT (JSON):
{{
    "subject_options": [
        "Subject 1 - completely fresh personalized subject, under 50 chars",
        "Subject 2 - different angle, entirely new wording",
        "Subject 3 - new question-based or trigger-based subject"
    ],
    "body": "The completely new email body formatted with \\n\\n for paragraph breaks - highly consultative, exploratory, ends with a polite 'I was wondering if it might be useful' CTA and a gentle soft exit.",
    "personalization_elements": ["List specific elements you personalized based on the data"],
    "cta_used": "The exact time-based CTA phrase you used"
}}

IMPORTANT: Each subject line should be DIFFERENT in approach. Don't just rephrase the same thing.
Make the email feel like you actually researched this person. Use genuine references, no marketing fluff."""
        
        system = """You are an elite B2B sales copywriter known for emails that get responses. 
Your emails are:
- Personalized (not generic "I came across your company")
- Concise (respect the reader's time)
- Value-focused (lead with insight, not pitch)
- Professional (never apologetic, always confident)
- Time-conscious (respects their schedule but assumes value)
- Action-oriented (clear, professional time-based CTA)

You never make unverified claims or use pushy language. You use the available intelligence to create genuine connections."""
        
        try:
            result = await self.openai.chat_json(prompt=prompt, system=system, temperature=0.8)
            return result
        except Exception as e:
            logger.error("LLM generation failed", error=str(e))
            return self._fallback_draft(context)
    
    def _fallback_draft(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a personalized fallback draft if LLM fails."""
        
        first_name = context.get("first_name", "there")
        company = context.get("company", "your company")
        role = context.get("role", "")
        industry = context.get("industry", "")
        triggers = context.get("triggers", [])
        linkedin_topics = context.get("linkedin_topics", [])
        pain_hypothesis = context.get("pain_hypothesis", "streamlining operations")
        your_positioning = context.get("your_positioning", "help companies scale efficiently")
        
        # Build a personalized hook based on available data
        hook = ""
        if triggers and len(triggers) > 0:
            trigger = triggers[0]
            trigger_type = trigger.get("type", "")
            if trigger_type == "funding":
                hook = f"Congratulations on the recent funding news! Scaling teams quickly after a raise is always a challenge."
            elif trigger_type == "hiring":
                hook = f"I noticed {company} is actively hiring—sounds like you're in growth mode."
            elif trigger_type == "expansion":
                hook = f"Saw that {company} is expanding into new markets—exciting times!"
            else:
                hook = f"I've been following {company}'s growth and wanted to reach out."
        elif linkedin_topics and len(linkedin_topics) > 0:
            topic = linkedin_topics[0]
            hook = f"I noticed your focus on {topic}—it's a topic we're seeing a lot of interest in."
        elif role:
            hook = f"As someone leading {role.lower()} at {company}, you're probably thinking about {pain_hypothesis}."
        else:
            hook = f"I came across {company} and was impressed by what you're building."
        
        # Build role-specific opening
        role_hook = ""
        if role:
            role_lower = role.lower()
            if "manager" in role_lower or "director" in role_lower or "vp" in role_lower:
                role_hook = "I imagine you're constantly balancing team performance while keeping operations efficient."
            elif "founder" in role_lower or "ceo" in role_lower or "cto" in role_lower:
                role_hook = "Building and scaling a company requires wearing many hats—especially when it comes to technology decisions."
            elif "analyst" in role_lower or "engineer" in role_lower:
                role_hook = "I know how important it is to have the right tools and processes in place to do your best work."
        
        # Create varied, compelling subject lines
        subject_options = [
            f"Quick thought for {first_name}",
            f"{company}'s growth + a question",
            f"Noticed something about {company}",
        ]
        
        if triggers:
            subject_options[0] = f"Re: {company}'s recent news"
        if linkedin_topics:
            subject_options[1] = f"Your focus on {linkedin_topics[0][:20]}..."
        if industry:
            subject_options[2] = f"How {industry} leaders are approaching this"
        
        # Build the body with proper paragraph breaks
        paragraphs = [f"Hi {first_name},"]
        
        paragraphs.append(hook)
        
        if role_hook:
            paragraphs.append(role_hook)
        
        # Value proposition paragraph
        value_prop = f"We work with companies like yours to help streamline processes, reduce operational overhead, and deliver faster time-to-value."
        paragraphs.append(value_prop)
        
        # CTA paragraph
        cta = "Would you be open to a quick 15-minute call next week to see if there's a potential fit? No pressure at all — happy to share a few insights either way."
        paragraphs.append(cta)
        
        # Sign off
        paragraphs.append("Best regards,")
        
        # Join with double newlines for proper paragraph spacing
        body = "\n\n".join(paragraphs)
        
        return {
            "subject_options": subject_options,
            "body": body,
            "personalization_elements": [
                "company name", 
                "first name",
                "role-based hook" if role else "industry context",
                "trigger/topic reference" if (triggers or linkedin_topics) else "growth narrative"
            ],
            "cta_used": "low-pressure 15-minute call request",
            "is_fallback": True,
        }
    
    def _convert_to_html(self, text: str) -> str:
        """Convert plain text with newlines to HTML paragraphs for Quill editor."""
        if not text:
            return ""
        
        # If already HTML, return as-is
        if "<p>" in text or "<br" in text:
            return text
        
        # Split by double newlines (paragraph breaks)
        paragraphs = text.split("\n\n")
        
        # Wrap each paragraph in <p> tags
        html_paragraphs = []
        for para in paragraphs:
            # Handle single newlines within paragraphs as <br>
            para = para.strip()
            if para:
                # Replace single newlines with <br>
                para = para.replace("\n", "<br>")
                html_paragraphs.append(f"<p>{para}</p>")
        
        return "".join(html_paragraphs)
    
    def _validate_draft(
        self, 
        draft: Dict[str, Any],
        strategy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate and clean up the generated draft."""
        
        # Ensure we have required fields
        if "subject_options" not in draft or not draft["subject_options"]:
            draft["subject_options"] = ["Quick question", "Thought for you", "Brief idea"]
        
        if "body" not in draft or not draft["body"]:
            draft = self._fallback_draft({})
        
        # Validate subject lengths
        draft["subject_options"] = [
            subj[:60] for subj in draft["subject_options"]
        ]
        
        # Validate body length (rough word count)
        body = draft.get("body", "")
        word_count = len(body.split())
        if word_count > 200:
            # Attempt to truncate at a natural break
            sentences = body.split(".")
            truncated = []
            count = 0
            for sentence in sentences:
                sentence_words = len(sentence.split())
                if count + sentence_words > 150:
                    break
                truncated.append(sentence)
                count += sentence_words
            
            if truncated:
                draft["body"] = ". ".join(truncated) + "."
                draft["was_truncated"] = True
        
        # Convert body to HTML for Quill editor so it maintains proper structure and spacing
        draft["body"] = self._convert_to_html(str(draft.get("body", "")))
        
        draft["word_count"] = len(draft.get("body", "").split())
        
        return draft
    
    async def generate_sequence(
        self,
        lead_data: Dict[str, Any],
        intelligence: Dict[str, Any],
        your_company: Dict[str, Any],
        strategy: Optional[Dict[str, Any]] = None,
        touches: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate all touches in a sequence."""
        
        drafts = []
        
        for touch_num in range(1, touches + 1):
            draft = await self.generate_draft(
                lead_data=lead_data,
                intelligence=intelligence,
                your_company=your_company,
                strategy=strategy,
                touch_number=touch_num,
            )
            drafts.append(draft)
        
        return drafts
