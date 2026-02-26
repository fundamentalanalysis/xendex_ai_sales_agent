import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead

async def find_nithyo():
    async with engine.connect() as conn:
        stmt = select(Lead).where(Lead.company_name == 'Nithyo Infotech')
        res = await conn.execute(stmt)
        l = res.one_or_none()
        if l:
            print(f"Company: {l.company_name} | Status: {l.status} | Composite: {l.composite_score}")
        else:
            print("Nithyo Infotech not found")

if __name__ == "__main__":
    asyncio.run(find_nithyo())
