import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def check_conn():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT count(*) FROM pg_stat_activity"))
        count = res.scalar()
        print(f"Current DB connections: {count}")
        
        # Also check max_connections
        res = await conn.execute(text("SHOW max_connections"))
        max_c = res.scalar()
        print(f"Max connections: {max_c}")

if __name__ == "__main__":
    asyncio.run(check_conn())
