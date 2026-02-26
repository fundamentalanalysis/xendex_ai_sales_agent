import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead, LeadIntelligence
from app.workers.research_tasks import run_research_pipeline

async def rerun_research():
    try:
        leads_to_run = []
        async with engine.connect() as conn:
            stmt = select(Lead.id, Lead.company_name).where(Lead.company_name.in_(['Extend', 'Super Ordinary']))
            res = await conn.execute(stmt)
            leads_to_run = res.all()
            
        print(f"Found {len(leads_to_run)} leads to research.")
        for lead_id, company in leads_to_run:
            print(f"Running research for: {company} (ID: {lead_id})")
            # Call the inner sync/async directly, but it's bound as celery task.
            # However `run_research_pipeline` is decorated with @celery_app.task.
            # We can call the underlying logic directly or use .apply()
            # Wait, `run_research_pipeline` calls an internal `_run()` synchronously.
            result = run_research_pipeline.apply(args=(str(lead_id),))
            print(f"Result for {company}: {result.get()}")
            
    finally:
        await engine.dispose()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(rerun_research())
