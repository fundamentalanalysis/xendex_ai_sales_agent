import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def reset_stuck():
    async with engine.connect() as conn:
        # Reset leads researching for > 10 minutes
        threshold = datetime.utcnow() - timedelta(minutes=10)
        res = await conn.execute(
            text("UPDATE leads SET status = 'not_qualified' WHERE status = 'researching' AND updated_at < :t"),
            {"t": threshold}
        )
        await conn.commit()
        print(f"Reset {res.rowcount} leads from 'researching' to 'not_qualified'")

if __name__ == "__main__":
    asyncio.run(reset_stuck())
