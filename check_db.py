import os
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres.ksnqthumauezmcusszuy:xIVqclI5RvSzWbyT@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL)
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM content_items"))
        count = result.scalar()
        print(f"CONTENT_ITEMS_COUNT: {count}")
except Exception as e:
    print(f"ERROR: {e}")
