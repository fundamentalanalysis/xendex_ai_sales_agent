#!/usr/bin/env python
"""Simple database initialization script."""
import sys
import asyncio

# Add backend to path
sys.path.insert(0, '/d/AI_Sales_Agent/backend')

from app.models.base import Base
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def init_db():
    """Initialize the database."""
    engine = create_async_engine(settings.get_database_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            print("Creating all tables...")
            await conn.run_sync(Base.metadata.create_all)
            print("✅ All tables created/updated successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
