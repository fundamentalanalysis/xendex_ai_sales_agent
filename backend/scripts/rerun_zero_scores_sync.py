import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead
from app.workers.research_tasks import run_research_pipeline

# Do it synchronously to avoid asyncio.run() clash
def run_sync():
    import psycopg2
    # Since we can't easily query with async engine, let's just hardcode the IDs we found earlier
    leads = [
        ("Extend", "ea977566-e41d-4650-beb8-96a299a6f1c4"),
        ("Super Ordinary", "9fccb0b1-ee14-490c-9223-83e61819e4c2"),
        ("Extend", "c8030257-8c2c-4144-aba4-91adc3c53ebd")
    ]
    
    for company, lead_id in leads:
        print(f"Running research for: {company} (ID: {lead_id})")
        # Run the celery task logic synchronously (no .apply() used here, just direct call since it uses asyncio.run internally)
        result = run_research_pipeline(lead_id)
        print(f"Result for {company}: {result}")

if __name__ == "__main__":
    run_sync()
