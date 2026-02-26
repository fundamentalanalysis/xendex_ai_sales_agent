import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, company_name, status FROM leads LIMIT 10"))
        rows = res.all()
        for r in rows:
            print(f"ID: {r.id} | Company: {r.company_name} | Status: {r.status}")

if __name__ == "__main__":
    asyncio.run(check())
