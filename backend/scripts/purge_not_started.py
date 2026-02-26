import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import update
from app.models.lead import Lead

async def purge_not_started():
    async with engine.connect() as conn:
        # Convert all 'not_started' to 'qualified'
        stmt = update(Lead).where(Lead.status == 'not_started').values(status='qualified')
        res = await conn.execute(stmt)
        print(f"Converted {res.rowcount} leads from 'not_started' to 'qualified'")
        await conn.commit()

if __name__ == "__main__":
    asyncio.run(purge_not_started())
