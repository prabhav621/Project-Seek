import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure src is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.db.models import InterestVector

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

def seed_db():
    db = SessionLocal()
    try:
        for domain_data in INITIAL_DOMAINS:
            # Check if domain already exists
            existing = db.query(InterestVector).filter_by(domain=domain_data['domain']).first()
            if not existing:
                vector = InterestVector(**domain_data)
                db.add(vector)
        db.commit()
        print("Database seeded successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
