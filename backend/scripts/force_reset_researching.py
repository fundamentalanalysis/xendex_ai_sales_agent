import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def force_reset():
    async with engine.connect() as conn:
        res = await conn.execute(
            text("UPDATE leads SET status = 'new' WHERE status = 'researching'")
        )
        await conn.commit()
        print(f"Force reset {res.rowcount} leads to 'new'")

if __name__ == "__main__":
    asyncio.run(force_reset())
