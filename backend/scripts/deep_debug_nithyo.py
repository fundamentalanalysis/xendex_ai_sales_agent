import asyncio
import os
import sys
import json

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead, LeadIntelligence

async def debug_nithyo():
    async with engine.connect() as conn:
        stmt = select(Lead).where(Lead.company_name == 'Nithyo Infotech')
        res = await conn.execute(stmt)
        leads = res.all()
        print(f"Total Nithyo Infotech records: {len(leads)}")
        
        for l in leads:
            print(f"\n--- Lead ID: {l.id} ---")
            print(f"Company: {l.company_name}")
            print(f"Status: {l.status}")
            print(f"Composite Score: {l.composite_score}")
            print(f"LinkedIn URL: {l.linkedin_url}")
            
            # Check intelligence
            intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == l.id)
            intel_res = await conn.execute(intel_stmt)
            intel = intel_res.one_or_none()
            
            if intel:
                print(f"Intelligence ID: {intel.id}")
                print(f"LinkedIn Role: {intel.linkedin_role}")
                print(f"LinkedIn Seniority: {intel.linkedin_seniority}")
                print(f"LinkedIn Lead Score: {intel.linkedin_lead_score}")
                print(f"Intelligence Researched At: {intel.researched_at}")
            else:
                print("No intelligence record found.")

if __name__ == "__main__":
    asyncio.run(debug_nithyo())
