import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select, func
from app.models.lead import Lead

async def check_all():
    async with engine.connect() as conn:
        stmt = select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        res = await conn.execute(stmt)
        rows = res.all()
        print("Lead counts by status:")
        for status, count in rows:
            print(f"  {status}: {count}")

if __name__ == "__main__":
    asyncio.run(check_all())
