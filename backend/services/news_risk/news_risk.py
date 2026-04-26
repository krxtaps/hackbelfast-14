from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from db.database import create_db_and_tables, engine
from db.models import NewsIncident
from services.geo import haversine_m


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # RSS dates vary; keep simple best-effort parse.
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def compute_news_risk(
    *,
    lat: float | None = None,
    lng: float | None = None,
    street_id: str | None = None,
    radius_m: float = 300.0,
    lookback_hours: int = 72,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Returns an aggregate risk score (0-100) based on recent news incidents.
    This is intended as a *separate* signal that can optionally be blended.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    create_db_and_tables()

    with Session(engine) as session:
        incidents: List[NewsIncident] = session.exec(
            select(NewsIncident).order_by(NewsIncident.id.desc()).limit(limit)
        ).all()

    weighted = 0.0
    used = 0
    items = []
    for inc in incidents:
        dt = _parse_dt(inc.published_at)
        if dt and dt < cutoff:
            continue

        if street_id and inc.street_id and inc.street_id != street_id:
            continue
        if lat is not None and lng is not None and inc.lat is not None and inc.lng is not None:
            if haversine_m(lat, lng, inc.lat, inc.lng) > radius_m:
                continue

        severity = inc.severity or 1
        # Recency decay: 1.0 today -> 0.3 after 72h
        age_h = ((now - dt).total_seconds() / 3600.0) if dt else 72.0
        decay = max(0.3, 1.0 - (age_h / max(1.0, lookback_hours)) * 0.7)
        weighted += severity * decay
        used += 1
        items.append(
            {
                "source": inc.source,
                "title": inc.title,
                "url": inc.url,
                "published_at": inc.published_at,
                "category": inc.category,
                "severity": severity,
                "location_text": inc.location_text,
                "summary": inc.summary,
                "decay": round(decay, 3),
                "street_id": inc.street_id,
                "street_name": inc.street_name,
                "lat": inc.lat,
                "lng": inc.lng,
            }
        )

    # Convert weighted severity into 0-100 "risk" (higher = more risk)
    # Tuned to be conservative.
    risk = min(100, round(weighted * 6.0, 1))
    return {
        "risk": risk,
        "radius_m": radius_m,
        "street_id": street_id,
        "lookback_hours": lookback_hours,
        "incidents_used": used,
        "items": items,
    }


def news_penalty_points(
    *,
    lat: float | None = None,
    lng: float | None = None,
    street_id: str | None = None,
    lookback_hours: int = 72,
) -> Dict[str, Any]:
    """
    Convert news risk into a small penalty for safety score blending.
    """
    res = compute_news_risk(
        lat=lat,
        lng=lng,
        street_id=street_id,
        lookback_hours=lookback_hours,
        limit=100,
    )
    risk = float(res.get("risk", 0.0))
    # Conservative: max 12-point penalty.
    penalty = round(min(12.0, risk * 0.12), 2)
    res["penalty_points"] = penalty
    return res

