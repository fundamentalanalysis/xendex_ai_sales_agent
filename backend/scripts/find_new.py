import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead

async def find_new():
    async with engine.connect() as conn:
        stmt = select(Lead.id, Lead.company_name).where(Lead.status == 'new')
        res = await conn.execute(stmt)
        row = res.fetchone()
        if row:
            print(f"New Lead ID: {row[0]} ({row[1]})")
        else:
            print("No new leads found.")

if __name__ == "__main__":
    asyncio.run(find_new())
