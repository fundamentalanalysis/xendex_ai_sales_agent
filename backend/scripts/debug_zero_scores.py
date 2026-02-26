import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead, LeadIntelligence

async def debug_leads():
    try:
        async with engine.connect() as conn:
            stmt = select(Lead).filter(Lead.company_name.in_(['Extend', 'Super Ordinary']))
            res = await conn.execute(stmt)
            leads = res.all()
            output = [f"Total target leads: {len(leads)}\n"]
            
            for l in leads:
                output.append(f"\n--- Lead ID: {l.id} ---")
                output.append(f"Company: {l.company_name}")
                output.append(f"Name: {l.first_name} {l.last_name}")
                output.append(f"Status: {l.status}")
                output.append(f"Domains: {l.company_domain}")
                output.append(f"Scores: None" if l.fit_score is None else f"Scores: Fit: {l.fit_score}, Ready: {l.readiness_score}, Intent: {l.intent_score}, Comp: {l.composite_score}")
                output.append(f"LinkedIn URL: {l.linkedin_url}")
                output.append(f"Updated At: {l.updated_at}")
                
                intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == l.id)
                intel_res = await conn.execute(intel_stmt)
                intel = intel_res.one_or_none()
                if intel:
                    output.append(f"Intel found! ID: {intel.id}")
                else:
                    output.append(f"No intelligence record.")
                
            print("\n".join(output))
    finally:
        await engine.dispose()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_leads())
