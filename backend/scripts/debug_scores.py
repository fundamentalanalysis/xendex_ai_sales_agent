import asyncio
import os
import sys
sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import text

async def debug():
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT 
                l.company_name, l.status,
                ROUND(CAST(l.fit_score AS numeric), 2) as fit,
                ROUND(CAST(l.composite_score AS numeric), 2) as composite,
                l.researched_at IS NOT NULL as is_researched,
                (li.id IS NOT NULL) as has_intel,
                (li.lead_offerings IS NOT NULL) as has_offerings
            FROM leads l
            LEFT JOIN lead_intelligence li ON li.lead_id = l.id
            ORDER BY l.company_name
        """))
        rows = res.fetchall()
        print(f"{'Company':<25} {'Status':<15} {'Fit':>5} {'Comp':>5} {'InDB':>6} {'Intel':>6} {'Offers':>7}")
        print("-" * 75)
        for r in rows:
            print(f"{r[0]:<25} {r[1]:<15} {str(r[2]):>5} {str(r[3]):>5} {str(r[4]):>6} {str(r[5]):>6} {str(r[6]):>7}")

if __name__ == "__main__":
    asyncio.run(debug())
