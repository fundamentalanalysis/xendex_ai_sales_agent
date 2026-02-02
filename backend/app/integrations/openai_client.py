"""Azure OpenAI client wrapper for GPT-4 interactions."""
import json
from typing import Any, Dict, List, Optional
import structlog
from openai import AsyncAzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


logger = structlog.get_logger()


class OpenAIClient:
    """Wrapper for Azure OpenAI API with retry logic and JSON parsing."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        self.api_key = api_key or settings.azure_ai_api_key
        self.endpoint = endpoint or settings.azure_ai_endpoint
        self.deployment = deployment or settings.azure_openai_deployment
        
        self.client = AsyncAzureOpenAI(
            api_key=self.api_key,
            api_version="2024-02-15-preview",
            azure_endpoint=self.endpoint,
        ) if self.api_key else None
    
    @property
    def is_configured(self) -> bool:
        """Check if Azure OpenAI is configured."""
        return bool(self.api_key and self.endpoint)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        deployment: Optional[str] = None,
    ) -> str:
        """
        Send a chat completion request to Azure OpenAI.
        
        Args:
            prompt: User prompt
            system: System message
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            deployment: Specific deployment to use (defaults to configured)
            
        Returns:
            Generated text response
        """
        if not self.client:
            raise ValueError("Azure OpenAI not configured")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=deployment or self.deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            return response.choices[0].message.content or ""
            
        except Exception as e:
            logger.error("Azure OpenAI API error", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def chat_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,  # Lower for JSON
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request expecting JSON response.
        
        Args:
            prompt: User prompt (should request JSON format)
            system: System message
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Parsed JSON response as dict
        """
        if not self.client:
            raise ValueError("Azure OpenAI not configured")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response", error=str(e))
            # Try to extract JSON from the response
            content = response.choices[0].message.content or ""
            return self._extract_json(content)
            
        except Exception as e:
            logger.error("Azure OpenAI API error", error=str(e))
            raise
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Try to extract JSON from text that might have extra content."""
        # Try to find JSON block
        import re
        
        # Look for ```json ... ``` blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Look for { ... } blocks
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass
        
        logger.warning("Could not extract JSON from response")
        return {"error": "Failed to parse JSON", "raw": text[:500]}
    
    async def generate_email(
        self,
        context: Dict[str, Any],
        template: Optional[str] = None,
        subject_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Generate an email with subject options.
        
        Args:
            context: Email context (lead info, strategy, evidence)
            template: Optional template to use
            subject_count: Number of subject line options
            
        Returns:
            Dict with subject_options and body
        """
        prompt = self._build_email_prompt(context, template, subject_count)
        
        system = """You are an expert B2B sales copywriter. Write personalized, concise emails that:
1. Open with a relevant hook (trigger, insight, or question)
2. Connect to a specific pain point or opportunity
3. Provide brief proof/credibility
4. End with a clear, low-friction CTA
5. Keep it under 150 words

Never make claims you can't verify. Be professional but not stiff."""
        
        return await self.chat_json(prompt=prompt, system=system)
    
    def _build_email_prompt(
        self,
        context: Dict[str, Any],
        template: Optional[str],
        subject_count: int,
    ) -> str:
        """Build the email generation prompt."""
        
        prompt = f"""Generate a B2B sales email based on this context:

**Lead Info:**
- Name: {context.get('first_name', 'there')} {context.get('last_name', '')}
- Role: {context.get('role', 'Unknown')}
- Company: {context.get('company', 'Unknown')}
- Industry: {context.get('industry', 'Unknown')}

**Strategy:**
- Angle: {context.get('angle', 'value-led')}
- Pain Hypothesis: {context.get('pain_hypothesis', 'Unknown')}
- CTA Type: {context.get('cta', 'reply')}
- Tone: {context.get('tone', 'professional')}
- Personalization: {context.get('personalization_mode', 'medium')}

**Evidence/Triggers:**
{json.dumps(context.get('evidence', {}), indent=2)}

**Your Company:**
- Services: {context.get('your_services', 'consulting services')}
- Positioning: {context.get('your_positioning', '')}

"""
        
        if template:
            prompt += f"""
**Template to Follow:**
{template}
"""
        
        prompt += f"""
Generate:
1. {subject_count} subject line options (varied approaches)
2. Email body (under 150 words)

Respond in JSON:
{{
    "subject_options": ["Subject 1", "Subject 2", "Subject 3"],
    "body": "Email body here...",
    "personalization_elements": ["element 1", "element 2"],
    "cta_used": "The CTA used"
}}
"""
        return prompt
