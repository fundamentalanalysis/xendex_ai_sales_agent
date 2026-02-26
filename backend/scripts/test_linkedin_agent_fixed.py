import asyncio
import os
import sys
import json

sys.path.append(os.getcwd())

# Set Windows Policy for ProactorEventLoop if needed (default in 3.8+)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.agents.linkedin_agent import LinkedInAgent
from app.config import settings

async def test_linkedin():
    agent = LinkedInAgent()
    url = "https://www.linkedin.com/in/taylormax/"  # From Nithyo lead
    
    print(f"Testing LinkedIn Agent for: {url}")
    try:
        result = await agent.run(
            linkedin_url=url,
            lead_title="Chief Technology Officer",
            lead_company="Nithyo Infotech"
        )
        print("\n--- LinkedIn Result ---")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error during agent run: {e}")
    finally:
        # Cleanup browser if any (though agent.run handles it)
        pass

if __name__ == "__main__":
    asyncio.run(test_linkedin())
