import asyncio
from sqlalchemy import text
from app.dependencies import async_session_maker

async def main():
    try:
        async with async_session_maker() as db:
            result = await db.execute(text("UPDATE leads SET status = 'not_qualified' WHERE status IN ('qualified', 'unqualified', 'not_qualified') AND composite_score < 0.60;"))
            await db.commit()
            print(f"Demoted {result.rowcount} stale unqualified leads successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
