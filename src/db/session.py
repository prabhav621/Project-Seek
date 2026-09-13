import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# We prefer DIRECT_URL for SQLAlchemy if available, fallback to DATABASE_URL, then localhost
DATABASE_URL = os.getenv("DIRECT_URL", os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"))

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
