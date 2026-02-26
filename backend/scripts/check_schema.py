import asyncio
import os
import sys
from sqlalchemy import text

sys.path.append(os.getcwd())

from app.dependencies import engine

async def check_schema():
    async with engine.connect() as conn:
        # Check 'leads' table default for 'status'
        res = await conn.execute(text("SHOW CREATE TABLE leads"))
        table_def = res.fetchone()
        print(f"Table Definition:\n{table_def[1]}")

if __name__ == "__main__":
    asyncio.run(check_schema())
