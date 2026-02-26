import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import update
from app.models.lead import Lead

async def force_qualified():
    async with engine.connect() as conn:
        stmt = update(Lead).where(Lead.company_name == 'Nithyo Infotech').values(status='qualified')
        res = await conn.execute(stmt)
        print(f"Force updated {res.rowcount} leads to 'qualified'")
        await conn.commit()

if __name__ == "__main__":
    asyncio.run(force_qualified())
