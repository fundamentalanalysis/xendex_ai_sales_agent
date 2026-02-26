"""
Fix zero scores AND trigger re-research for affected leads.
"""
import asyncio
import os
import sys
sys.path.append(os.getcwd())

async def fix_and_retrigger():
    from app.dependencies import engine
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Clear zero scores so fix_research_endpoint works
        result = await conn.execute(text("""
            UPDATE leads
            SET 
                fit_score = NULL,
                readiness_score = NULL,
                intent_score = NULL,
                composite_score = NULL,
                researched_at = NULL,
                status = 'new'
            WHERE 
                (fit_score = 0 OR fit_score IS NULL)
                AND (composite_score = 0 OR composite_score IS NULL)
            RETURNING id, company_name
        """))
        fixed = result.fetchall()
        
        if not fixed:
            print("No zero-score leads found to fix.")
        else:
            for row in fixed:
                print(f"Reset: {row[1]} (id={row[0]})")

    print("\nNow triggering research for reset leads via API...")
    
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        # Get leads with status = new
        resp = await client.get("http://localhost:8000/api/v1/leads/?limit=100")
        data = resp.json()
        
        leads_to_research = [
            l for l in data.get("items", [])
            if l.get("status") == "new" and not l.get("composite_score")
        ]
        
        print(f"\nFound {len(leads_to_research)} leads to research:")
        for lead in leads_to_research:
            print(f"  - {lead['company_name']} ({lead['id'][:8]}...)")
            r = await client.post(
                f"http://localhost:8000/api/v1/leads/{lead['id']}/research",
                json={"force_refresh": True}
            )
            result = r.json()
            print(f"    → Research queued: task_id={result.get('task_id', 'N/A')[:16]}...")
        
        print("\n✅ Research triggered! Watch Celery logs for progress.")
        print("   The research pipeline will run LinkedIn scraping with your new cookie.")

if __name__ == "__main__":
    asyncio.run(fix_and_retrigger())
