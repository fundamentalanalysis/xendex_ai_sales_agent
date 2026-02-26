import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead

async def debug_leads():
    async with engine.connect() as conn:
        stmt = select(Lead).limit(10)
        res = await conn.execute(stmt)
        leads = res.all()
        print(f"Total leads found: {len(leads)}")
        for l in leads:
            print(f"Company: {l.company_name} | Status: {l.status} | Composite: {l.composite_score}")

if __name__ == "__main__":
    asyncio.run(debug_leads())
