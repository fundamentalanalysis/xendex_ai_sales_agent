import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def check_stuck():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, company_name, status, updated_at FROM leads WHERE status = 'researching'"))
        rows = res.all()
        print(f"Found {len(rows)} leads currently in 'researching' status.")
        for r in rows:
            print(f"ID: {r.id} | Company: {r.company_name} | Updated At: {r.updated_at}")

if __name__ == "__main__":
    asyncio.run(check_stuck())
