import asyncio
from src.db.session import SyncSessionLocal
from src.db.models import ContentItem, DailyItem

def clean_twitter_data():
    print("🧹 Starting cleanup of corrupted Twitter ingestion data...")
    db = SyncSessionLocal()
    try:
        # Find all X/Twitter items
        items = db.query(ContentItem).filter(ContentItem.source_type == 'x_twitter').all()
        
        if not items:
            print("✅ No corrupted X/Twitter items found in the database.")
            return

        print(f"🗑️ Found {len(items)} corrupted Twitter items. Deleting...")
        for item in items:
            # Delete any associated DailyItem first (to prevent foreign key constraint errors)
            daily_items = db.query(DailyItem).filter(DailyItem.content_id == item.id).all()
            for d_item in daily_items:
                db.delete(d_item)
            
            # Now delete the content item
            db.delete(item)
            
        db.commit()
        print(f"✅ Successfully purged {len(items)} corrupted Twitter records.")
        print("Ready for re-ingestion with the new API proxy!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_twitter_data()
