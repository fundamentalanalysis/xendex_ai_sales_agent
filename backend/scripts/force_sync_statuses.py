import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select, update
from app.models.lead import Lead
from app.config import settings

async def force_fix():
    print(f"--- FORCING STATUS SYNC ---")
    async with engine.connect() as conn:
        # If composite_score >= 0.35, status MUST be 'qualified'
        stmt_q = update(Lead).where(
            Lead.composite_score >= settings.qualification_threshold
        ).values(status='qualified')
        res_q = await conn.execute(stmt_q)
        print(f"Force updated {res_q.rowcount} leads to 'qualified'")

        # If 0 < composite_score < 0.35, status MUST be 'not_qualified'
        stmt_nq = update(Lead).where(
            Lead.composite_score < settings.qualification_threshold,
            Lead.composite_score.isnot(None)
        ).values(status='not_qualified')
        res_nq = await conn.execute(stmt_nq)
        print(f"Force updated {res_nq.rowcount} leads to 'not_qualified'")

        await conn.commit()
    print("--- SYNC COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(force_fix())
