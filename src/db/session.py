import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL for SQLAlchemy connection, ensure it uses postgresql+asyncpg
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://seek_user:seek_password@localhost:5432/seek_db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# ─── Async Engine (for Telegram bot event loop, ingestion pipeline) ───
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

# ─── Sync Engine (for curator.py, drift_engine.py, Daily Forge) ───
# These modules use synchronous SQLAlchemy ORM patterns (db.query, db.commit)
# which are incompatible with AsyncSession.
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=3,
    max_overflow=2
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

async def get_db():
    async with SessionLocal() as db:
        yield db

