
import asyncio
from sqlalchemy import text
from app.dependencies import engine

async def migrate():
    print("Force applying schema changes...")
    async with engine.begin() as conn:
        try:
            # Drop the columns if they partially exist (clean slate) or just ensure they are there
            await conn.execute(text("ALTER TABLE lead_intelligence ADD COLUMN IF NOT EXISTS fit_breakdown JSONB;"))
            await conn.execute(text("ALTER TABLE lead_intelligence ADD COLUMN IF NOT EXISTS readiness_breakdown JSONB;"))
            print("✅ Columns added successfully.")
        except Exception as e:
            print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
