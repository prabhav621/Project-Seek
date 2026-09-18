import os
import sys
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Ensure src is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.db.models import InterestVector

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
engine = create_async_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

INITIAL_DOMAINS = [
    {'domain': 'system_architecture', 'weight': 0.85, 'is_blind_spot': False, 'is_graveyard': False},
    {'domain': 'ai_engineering', 'weight': 0.80, 'is_blind_spot': False, 'is_graveyard': False},
    {'domain': 'startup_strategy', 'weight': 0.75, 'is_blind_spot': False, 'is_graveyard': False},
    {'domain': 'scaling_infrastructure', 'weight': 0.70, 'is_blind_spot': True, 'is_graveyard': False},
    {'domain': 'product_design_ux', 'weight': 0.65, 'is_blind_spot': False, 'is_graveyard': False},
    {'domain': 'first_principles_thinking', 'weight': 0.60, 'is_blind_spot': False, 'is_graveyard': False},
    {'domain': 'ancient_philosophy_applied', 'weight': 0.45, 'is_blind_spot': False, 'is_graveyard': False},
    {'domain': 'growth_engineering', 'weight': 0.45, 'is_blind_spot': True, 'is_graveyard': False},
    {'domain': 'civic_tech_policy', 'weight': 0.35, 'is_blind_spot': True, 'is_graveyard': True},
    {'domain': 'investing_finance', 'weight': 0.30, 'is_blind_spot': False, 'is_graveyard': True},
    {'domain': 'political_systems', 'weight': 0.30, 'is_blind_spot': True, 'is_graveyard': True},
]

async def seed_db():
    async with SessionLocal() as db:
        try:
            for domain_data in INITIAL_DOMAINS:
                # Check if domain already exists
                existing = (await db.execute(select(InterestVector).filter_by(domain=domain_data['domain']))).scalars().first()
                if not existing:
                    vector = InterestVector(**domain_data)
                    db.add(vector)
            await db.commit()
            print("Database seeded successfully.")
        except Exception as e:
            await db.rollback()
            print(f"Error seeding database: {e}")

if __name__ == "__main__":
    asyncio.run(seed_db())
