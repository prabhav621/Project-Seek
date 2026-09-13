from sqlalchemy.orm import Session
from sqlalchemy import func, case, Float
from datetime import date
import logging

from src.db.models import DailyItem, InterestVector

logger = logging.getLogger(__name__)

def curate_daily_forge(db: Session, target_date: date) -> dict:
    """
    Selects the portfolio of daily items based on relevance, novelty, blind-spot boost, and recency.
    The portfolio includes:
      - 1 deep_kata
      - 2 quick_katas
      - 1 aphorism
      - 1 inversion_prompt
      - 1 curated_suggestion
    """
    
    # Subquery to calculate domain-based metrics per item
    # Joining item.domains (ARRAY) with InterestVector.domain using ANY()
    domain_metrics = db.query(
        DailyItem.id.label('item_id'),
        func.max(InterestVector.weight).label('max_weight'),
        func.bool_or(InterestVector.is_blind_spot).label('has_blind_spot')
    ).outerjoin(
        InterestVector, InterestVector.domain == func.any(DailyItem.domains)
    ).filter(
        DailyItem.forge_date.is_(None),
        DailyItem.engagement == 'pending'
    ).group_by(DailyItem.id).subquery()

    # Recency metric: created_at epoch divided by current epoch to get a 0-1 range
    current_epoch = func.extract('epoch', func.now())
    item_epoch = func.extract('epoch', DailyItem.created_at)
    
    # Calculate score according to the weights provided in the plan
    score_expr = (
        func.coalesce(domain_metrics.c.max_weight, 0.5) * 0.55 +
        func.random() * 0.20 +
        case((domain_metrics.c.has_blind_spot == True, 1.0), else_=0.0) * 0.15 +
        (item_epoch / current_epoch) * 0.10
    ).label('score')

    # Base query for candidates with their computed score
    candidates_query = db.query(
        DailyItem,
        score_expr
    ).join(
        domain_metrics, DailyItem.id == domain_metrics.c.item_id
    )

    portfolio = {}

    # 1. Select 1 deep_kata
    deep_kata = candidates_query.filter(DailyItem.item_type == 'deep_kata')\
                                .order_by(score_expr.desc())\
                                .first()
    if deep_kata:
        portfolio['deep_kata'] = deep_kata.DailyItem

    # 2. Select 2 quick_katas (try to select from different domains)
    quick_katas = candidates_query.filter(DailyItem.item_type == 'quick_kata')\
                                  .order_by(score_expr.desc())\
                                  .limit(10).all()
    selected_qks = []
    seen_domains = set()
    for qk_tuple in quick_katas:
        qk = qk_tuple.DailyItem
        qk_domains = set(qk.domains or [])
        # If no overlap in domains, or if we haven't found any yet
        if not seen_domains.intersection(qk_domains):
            selected_qks.append(qk)
            seen_domains.update(qk_domains)
            if len(selected_qks) == 2:
                break
                
    # Fallback if we couldn't find 2 with strictly different domains
    if len(selected_qks) < 2:
        for qk_tuple in quick_katas:
            qk = qk_tuple.DailyItem
            if qk not in selected_qks:
                selected_qks.append(qk)
                if len(selected_qks) == 2:
                    break
    
    portfolio['quick_katas'] = selected_qks

    # 3. Select 1 aphorism
    aphorism = candidates_query.filter(DailyItem.item_type == 'aphorism')\
                               .order_by(score_expr.desc())\
                               .first()
    if aphorism:
        portfolio['aphorism'] = aphorism.DailyItem

    # 4. Select 1 inversion_prompt (target highest-weight domain first)
    top_domain_row = db.query(InterestVector).order_by(InterestVector.weight.desc()).first()
    inversion = None
    if top_domain_row:
        # Try to find an inversion prompt specifically for this domain
        inversion = candidates_query.filter(
            DailyItem.item_type == 'inversion_prompt',
            top_domain_row.domain == func.any(DailyItem.domains)
        ).order_by(score_expr.desc()).first()
        
    if not inversion:
        # Fallback to the highest score overall
        inversion = candidates_query.filter(DailyItem.item_type == 'inversion_prompt')\
                                    .order_by(score_expr.desc()).first()
                                    
    if inversion:
        portfolio['inversion_prompt'] = inversion.DailyItem

    # 5. Select 1 curated_suggestion
    suggestion = candidates_query.filter(DailyItem.item_type == 'curated_suggestion')\
                                 .order_by(score_expr.desc())\
                                 .first()
    if suggestion:
        portfolio['curated_suggestion'] = suggestion.DailyItem
        
    # Mark all selected items with the target forge_date
    for key, item in portfolio.items():
        if isinstance(item, list):
            for i in item:
                i.forge_date = target_date
        else:
            item.forge_date = target_date
            
    db.commit()
    
    return portfolio
