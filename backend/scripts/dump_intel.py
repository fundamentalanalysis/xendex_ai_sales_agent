import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead, LeadIntelligence

async def dump_intel():
    async with engine.connect() as conn:
        stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == '9fccb0b1-ee14-490c-9223-83e61819e4c2')
        res = await conn.execute(stmt)
        intel = res.one_or_none()
        if intel:
            print("--- LinkedIn Intel ---")
            print(f"Role: {intel.linkedin_role}")
            print(f"Seniority: {intel.linkedin_seniority}")
            print(f"Topics: {intel.linkedin_topics_30d}")
            print(f"Decision Power: {intel.linkedin_decision_power}")
            
            print("\n--- Lead Company Intel ---")
            print(f"Offerings: {intel.lead_offerings}")
            print(f"Pain Indicators: {intel.lead_pain_indicators}")
            print(f"Buying Signals: {intel.lead_buying_signals}")
            print(f"Tech Stack: {intel.lead_tech_stack}")
            
            print("\n--- Triggers ---")
            print(f"Triggers: {intel.triggers}")
            
        else:
            print("No intel found.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(dump_intel())
