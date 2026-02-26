import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def check_extend():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, status FROM leads WHERE company_name ILIKE '%Extend%'"))
        row = res.one_or_none()
        if row:
            print(f"STATUS_IS: {row.status}")
        else:
            print("NOT_FOUND")

if __name__ == "__main__":
    asyncio.run(check_extend())
