import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent
sys.path.append(str(src_path))

from db.session import SessionLocal
from intelligence.drift_engine import daily_decay

def run_decay():
    db = SessionLocal()
    try:
        print("Running daily decay...")
        daily_decay(db)
        print("Daily decay complete.")
    except Exception as e:
        print(f"Error running daily decay: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_decay()
