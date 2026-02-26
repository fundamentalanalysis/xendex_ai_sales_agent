import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead

async def check_not_started():
    async with engine.connect() as conn:
        stmt = select(Lead).where(Lead.status == 'not_started')
        res = await conn.execute(stmt)
        leads = res.all()
        print(f"Total 'not_started' leads: {len(leads)}")
        for l in leads:
            print(f"Company: {l.company_name} | Composite: {l.composite_score}")

if __name__ == "__main__":
    asyncio.run(check_not_started())
