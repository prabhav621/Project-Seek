import os
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres.ksnqthumauezmcusszuy:xIVqclI5RvSzWbyT@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

engine = create_engine(DATABASE_URL)
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result]
        print(f"TABLES: {tables}")
except Exception as e:
    print(f"ERROR: {e}")
