import asyncio
import os
import sys

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select, update
from app.models.lead import Lead
from app.config import settings

async def fix():
    print(f"--- STARTING STATUS FIX ---")
    print(f"Qualification Threshold: {settings.qualification_threshold}")
    
    async with engine.connect() as conn:
        # 1. Leads with high scores -> 'qualified'
        stmt1 = select(Lead).where(
            Lead.composite_score >= settings.qualification_threshold,
            Lead.status.in_(['not_started', 'new', 'researching', 'disqualified'])
        )
        res1 = await conn.execute(stmt1)
        to_qualify = res1.all()
        print(f"Found {len(to_qualify)} leads to mark as 'qualified'")
        
        if to_qualify:
            ids = [l.id for l in to_qualify]
            await conn.execute(update(Lead).where(Lead.id.in_(ids)).values(status='qualified'))
            print(f"Updated {len(ids)} leads to 'qualified'")

        # 2. Leads with low scores -> 'not_qualified'
        stmt2 = select(Lead).where(
            Lead.composite_score < settings.qualification_threshold,
            Lead.composite_score.isnot(None),
            Lead.status.in_(['not_started', 'new', 'researching', 'qualified'])
        )
        res2 = await conn.execute(stmt2)
        to_disqualify = res2.all()
        print(f"Found {len(to_disqualify)} leads to mark as 'not_qualified'")
        
        if to_disqualify:
            ids = [l.id for l in to_disqualify]
            await conn.execute(update(Lead).where(Lead.id.in_(ids)).values(status='not_qualified'))
            print(f"Updated {len(ids)} leads to 'not_qualified'")

        await conn.commit()
    print("--- STATUS FIX COMPLETE ---")

if __name__ == "__main__":
    try:
        asyncio.run(fix())
    except Exception as e:
        print(f"Error: {e}")
