from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
import logging

from src.db.models import InterestVector, DailyItem

logger = logging.getLogger(__name__)

ENGAGEMENT_MULTIPLIER = {
    'skipped':   0.0,
    'read':      1.0,
    'responded': 2.0,
    'debated':   3.0,
}

def update_drift(db: Session, item_id: str, engagement_type: str, reply_analysis: dict = None):
    """
    Updates the drift for domains based on engagement with a DailyItem.
    """
    item = db.query(DailyItem).filter(DailyItem.id == item_id).first()
    if not item or item.embedding is None:
        logger.warning(f"Item {item_id} not found or has no embedding.")
        return

    multiplier = ENGAGEMENT_MULTIPLIER.get(engagement_type, 1.0)
    now_tz = datetime.now(timezone.utc)

    # 1. Find nearest domains via cosine similarity
    # Using pgvector's cosine_distance
    distances = db.query(
        InterestVector,
        InterestVector.embedding.cosine_distance(item.embedding).label("distance")
    ).filter(InterestVector.embedding.is_not(None)).all()

    for domain, distance in distances:
        similarity = max(0.0, 1.0 - (distance or 0.0))
        boost = 0.1 * multiplier * similarity
        
        domain.weight = min(1.0, domain.weight + boost)
        domain.momentum = 0.7 * domain.momentum + 0.3 * boost
        domain.last_engaged = now_tz

    # 2. If reply_analysis exists, apply topic-level micro-boosts
    if reply_analysis and isinstance(reply_analysis, dict):
        topics = reply_analysis.get('topics_mentioned', [])
        # In a full implementation, we'd embed the topic and find nearest.
        # For now, we perform an exact match or assume the embedding is handled upstream.
        for topic in topics:
            matched_domain = db.query(InterestVector).filter(InterestVector.domain == topic).first()
            if matched_domain:
                matched_domain.weight = min(1.0, matched_domain.weight + 0.03)

    db.commit()

def daily_decay(db: Session):
    """
    Runs at midnight. Decays the weight of all domains.
    """
    db.query(InterestVector).update(
        {InterestVector.weight: func.greatest(0.05, InterestVector.weight - InterestVector.decay_rate)},
        synchronize_session=False
    )
    db.commit()
