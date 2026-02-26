import asyncio
import traceback
from sqlalchemy import select
from app.dependencies import async_session_maker
from app.models.lead import Lead
from app.services.research import run_research_background

async def main():
    lead_id = None
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(Lead).where(Lead.company_name == 'Nithyo Infotech'))
            lead = result.scalars().first()
            if lead:
                lead_id = str(lead.id)
                
        if not lead_id:
            print('Lead not found')
            return
            
        print(f'Using lead: {lead_id}')
        await run_research_background(lead_id)
        print('Research completed')
    except Exception as e:
        print(f"FAILED AT TOP LEVEL: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
