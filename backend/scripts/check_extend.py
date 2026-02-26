import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def check_extend():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, company_name, status, researched_at FROM leads WHERE company_name ILIKE '%Extend%'"))
        rows = res.all()
        for r in rows:
            print(f"ID: {r.id} | Company: {r.company_name} | Status: {r.status} | Researched At: {r.researched_at}")

if __name__ == "__main__":
    asyncio.run(check_extend())
