import sys
import asyncio
import traceback
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent
sys.path.append(str(src_path))

from db.session import SyncSessionLocal
from intelligence.drift_engine import daily_decay


async def run_decay():
    try:
        print("Running daily decay...")
        # daily_decay uses synchronous ORM (db.query, db.commit)
        # so we give it a sync session and run in a thread
        await asyncio.to_thread(_run_decay_sync)
        print("Daily decay complete.")
    except Exception as e:
        print(f"Error running daily decay: {e}")
        traceback.print_exc()


def _run_decay_sync():
    db = SyncSessionLocal()
    try:
        daily_decay(db)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(run_decay())
