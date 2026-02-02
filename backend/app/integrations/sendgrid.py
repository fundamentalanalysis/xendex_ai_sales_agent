"""Resend integration for email sending."""
from typing import Any, Dict, List, Optional
import structlog
import resend

from app.config import settings

logger = structlog.get_logger()


class EmailClient:
    """
    Client for Resend email API using the official SDK.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.resend_api_key
        # Ensure we set the API key globally for the SDK
        if self.api_key:
            resend.api_key = self.api_key
        
        self.from_email = settings.resend_from_email 
        self.from_name = settings.resend_from_name
        self.reply_to = settings.resend_reply_to
        # Developer email for testing (Resend restriction bypass)
        self.developer_email = "gudalapraveenkumar44@gmail.com"
    
    @property
    def is_configured(self) -> bool:
        """Check if Resend is configured."""
        return bool(self.api_key)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        to_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        custom_args: Optional[Dict[str, str]] = None,
        unsubscribe_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single email using Resend API SDK."""
        if not self.is_configured:
            logger.warning("Resend not configured")
            return {"success": False, "error": "Resend not configured"}
        
        try:
            # Construct the sender in "Name <email>" format
            from_header = f"{self.from_name} <{self.from_email}>"
            
            # Prepare HTML body
            html_body = self._text_to_html(body, unsubscribe_url)
            
            # Prepare params for Resend
            params = {
                "from": from_header,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": body,  # Include plain text fallback
            }

            actual_reply_to = reply_to or self.reply_to
            if actual_reply_to:
                params["reply_to"] = actual_reply_to
                
            # Execute send via SDK
            import asyncio
            
            # DEVELOPER BYPASS: If using onboarding address, check if we should redirect
            if self.from_email == "onboarding@resend.dev" and to_email != self.developer_email:
                print(f"[DEBUG] >>> RESEND SANDBOX: Redirecting email for {to_email} to {self.developer_email} to avoid domain error")
                params["to"] = [self.developer_email]
                params["subject"] = f"[TEST for {to_email}] {subject}"

            response = await asyncio.to_thread(resend.Emails.send, params)
            print(f"[DEBUG] >>> RESEND RESPONSE: {response}")
            
            # Resend SDK returns a dict like {'id': '...'}
            message_id = response.get("id")
            
            logger.info(
                "Email sent via Resend",
                to=to_email,
                subject=subject[:50],
                message_id=message_id,
            )
            
            return {
                "success": True,
                "message_id": message_id,
            }
            
        except Exception as e:
            print(f"[ERROR] >>> RESEND API ERROR: {str(e)}")
            logger.error("Resend send error", error=str(e), to=to_email)
            return {"success": False, "error": str(e)}
    
    async def send_batch(
        self,
        emails: List[Dict[str, Any]],
        max_concurrent: int = 10,
    ) -> List[Dict[str, Any]]:
        """Send multiple emails."""
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def send_one(email_data: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                result = await self.send_email(**email_data)
                result["to_email"] = email_data["to_email"]
                return result
        
        tasks = [send_one(email) for email in emails]
        return await asyncio.gather(*tasks)

    def _text_to_html(self, text: str, unsubscribe_url: Optional[str] = None) -> str:
        """Convert plain text email to HTML with proper formatting.
        
        If the text is already HTML (contains <p> or <br> tags), it will be used directly.
        Otherwise, plain text will be escaped and converted to HTML.
        """
        import html
        
        # Check if the text is already HTML
        is_html = "<p>" in text or "<br>" in text or "<br/>" in text or "<div>" in text
        
        if is_html:
            # Already HTML - use as-is (don't escape)
            html_body = text
        else:
            # Plain text - escape and convert newlines to <br>
            escaped = html.escape(text)
            html_body = escaped.replace("\n", "<br>\n")
        
        footer = ""
        if unsubscribe_url:
            footer = f"""
<br><br>
<p style="font-size: 12px; color: #666;">
    <a href="{unsubscribe_url}" style="color: #666;">Unsubscribe</a>
</p>
"""
        return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
    {html_body}
    {footer}
</body>
</html>
"""

    async def validate_email(self, email: str) -> Dict[str, Any]:
        """Resend does not have a public free validation API like SendGrid, stubbing."""
        return {"valid": True, "reason": "Validation not supported by Resend driver"}

    async def get_domain_stats(self) -> Dict[str, Any]:
        """Stub for domain stats."""
        return {"requests": 0, "delivered": 0}

    async def list_received_emails(self) -> Dict[str, Any]:
        """List received emails using Resend receiving API."""
        if not self.is_configured:
            logger.warning("Resend not configured")
            return {"success": False, "error": "Resend not configured"}
        
        try:
            import asyncio
            response = await asyncio.to_thread(resend.Emails.Receiving.list)
            return {"success": True, "data": response}
        except Exception as e:
            logger.error("Resend receiving list error", error=str(e))
            return {"success": False, "error": str(e)}

    async def get_received_email(self, email_id: str) -> Dict[str, Any]:
        """Get a specific received email using Resend receiving API."""
        if not self.is_configured:
            logger.warning("Resend not configured")
            return {"success": False, "error": "Resend not configured"}
        
        try:
            import asyncio
            response = await asyncio.to_thread(resend.Emails.Receiving.get, email_id=email_id)
            return {"success": True, "data": response}
        except Exception as e:
            logger.error("Resend receiving get error", error=str(e), email_id=email_id)
            return {"success": False, "error": str(e)}
