import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead

async def check():
    async with engine.connect() as conn:
        stmt = select(Lead.persona, Lead.industry).where(Lead.company_name == 'Nithyo Infotech')
        res = await conn.execute(stmt)
        row = res.fetchone()
        print(f"Persona: {row[0]}")
        print(f"Industry: {row[1]}")

if __name__ == "__main__":
    asyncio.run(check())
