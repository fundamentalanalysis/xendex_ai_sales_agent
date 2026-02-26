import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.agents.linkedin_agent import LinkedInAgent
from app.config import settings

async def test_linkedin():
    agent = LinkedInAgent()
    url = "https://www.linkedin.com/in/taylormax/"  # From Nithyo lead
    
    print(f"Testing LinkedIn Agent for: {url}")
    result = await agent.run(
        linkedin_url=url,
        lead_title="Chief Technology Officer",
        lead_company="Nithyo Infotech"
    )
    
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(test_linkedin())
