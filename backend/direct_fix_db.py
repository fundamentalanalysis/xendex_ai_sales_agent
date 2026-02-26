
import asyncio
import asyncpg
import os

async def run_fix():
    print("Directly connecting to DB to fix schema...")
    
    # Simple manual parse of .env
    env = {}
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    
    try:
        conn = await asyncpg.connect(
            user=env.get("DB_USER"),
            password=env.get("DB_PASS"),
            database=env.get("DB_NAME"),
            host=env.get("DB_HOST"),
            port=env.get("DB_PORT")
        )
        print("Connected.")
        await conn.execute("ALTER TABLE lead_intelligence ADD COLUMN IF NOT EXISTS fit_breakdown JSONB;")
        await conn.execute("ALTER TABLE lead_intelligence ADD COLUMN IF NOT EXISTS readiness_breakdown JSONB;")
        print("✅ Columns added safely using direct connection.")
        await conn.close()
    except Exception as e:
        print(f"❌ Direct fix failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_fix())
