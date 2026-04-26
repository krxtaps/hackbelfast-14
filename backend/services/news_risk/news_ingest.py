import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import feedparser
import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from sqlmodel import Session, select

from db.database import create_db_and_tables, engine
from db.models import NewsIncident
from services.news_risk.news_geocode import resolve_news_location_to_street


@dataclass(frozen=True)
class RssSource:
    name: str
    url: str


DEFAULT_SOURCES: List[RssSource] = [
    # Add/replace sources as desired. These are safe defaults to start with.
    RssSource("BBC News NI", "https://feeds.bbci.co.uk/news/northern_ireland/rss.xml"),
    RssSource("Belfast Live", "https://www.belfastlive.co.uk/all-about/crime?service=rss"),
]


FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
load_dotenv()
BELFAST_KEYWORDS = [
    "belfast",
    "botanic",
    "queens quarter",
    "queen's quarter",
    "stranmillis",
    "ormeau",
    "lisburn road",
    "university road",
    "donegall",
    "sandy row",
    "bt7",
]


def _has_featherless_key() -> bool:
    return bool(os.getenv("FEATHERLESS_API_KEY"))


def _parse_published_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_recent_and_relevant(
    *,
    title: str,
    snippet: str | None,
    published_at: str | None,
    lookback_hours: int,
    belfast_only: bool,
) -> bool:
    dt = _parse_published_at(published_at)
    if dt:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        if dt < cutoff:
            return False

    if not belfast_only:
        return True

    haystack = f"{title} {snippet or ''}".lower()
    return any(keyword in haystack for keyword in BELFAST_KEYWORDS)


async def _featherless_extract_incident_fields(
    *,
    title: str,
    url: str,
    source: str,
    published_at: str | None,
    snippet: str | None,
    model: str = "Qwen/Qwen2.5-7B-Instruct",
) -> Dict[str, Any]:
    """
    Best-effort extraction of location/category/severity. Returns dict fields.
    If no API key is set, returns heuristic defaults.
    """
    if not _has_featherless_key():
        # Heuristic fallback: keep deterministic + free
        lowered = (title or "").lower()
        category = "anti-social" if "anti-social" in lowered else "crime" if "crime" in lowered else "unknown"
        severity = 2 if category in ("anti-social", "crime") else 1
        return {
            "location_text": None,
            "street_name": None,
            "lat": None,
            "lng": None,
            "category": category,
            "severity": severity,
            "summary": None,
        }

    system = (
        "You extract structured incident metadata from local news headlines.\n"
        "Return ONLY valid JSON with keys: location_text (string|null), street_name (string|null), "
        "lat (number|null), lng (number|null), category (string), severity (int 1-5), summary (string|null).\n"
        "Category should be one of: violent-crime, robbery, public-order, drugs, anti-social-behaviour, burglary, theft, unknown.\n"
        "Severity: 1=low concern, 5=high concern.\n"
        "If precise coordinates are not available, set lat/lng null and try street_name.\n"
    )
    user = {
        "source": source,
        "title": title,
        "url": url,
        "published_at": published_at,
        "snippet": snippet,
        "scope_note": "We care about Belfast, especially Botanic area.",
    }

    # Primary path: LangChain client against Featherless OpenAI-compatible endpoint.
    try:
        llm = ChatOpenAI(
            api_key=os.getenv("FEATHERLESS_API_KEY"),
            base_url=FEATHERLESS_BASE_URL,
            model=model,
            temperature=0.0,
            max_tokens=300,
        )
        resp = await llm.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=json.dumps(user)),
            ]
        )
        parsed = json.loads(resp.content)
    except Exception:
        # Fallback: direct HTTP call if LangChain path fails
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
            "temperature": 0.0,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {os.getenv('FEATHERLESS_API_KEY')}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("FEATHERLESS_HTTP_REFERER", "http://localhost"),
            "X-Title": os.getenv("FEATHERLESS_X_TITLE", "SafeWalk"),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{FEATHERLESS_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

    return {
        "location_text": parsed.get("location_text"),
        "street_name": parsed.get("street_name"),
        "lat": parsed.get("lat"),
        "lng": parsed.get("lng"),
        "category": parsed.get("category") or "unknown",
        "severity": parsed.get("severity"),
        "summary": parsed.get("summary"),
    }


async def ingest_sources(
    sources: Optional[List[RssSource]] = None,
    limit_per_source: int = 30,
    lookback_hours: int = 72,
    belfast_only: bool = True,
    require_street_match: bool = False,
) -> Dict[str, Any]:
    """
    Fetch RSS feeds, extract incident fields, and upsert into SQLite.
    """
    sources = sources or DEFAULT_SOURCES
    create_db_and_tables()
    inserted = 0
    skipped = 0
    filtered_out = 0
    unmatched_street = 0

    for src in sources:
        feed = feedparser.parse(src.url)
        entries = (feed.entries or [])[:limit_per_source]

        for e in entries:
            url = e.get("link") or ""
            title = e.get("title") or ""
            if not url or not title:
                skipped += 1
                continue

            published = e.get("published") or e.get("updated")
            snippet = e.get("summary") or e.get("description")
            if not _is_recent_and_relevant(
                title=title,
                snippet=snippet,
                published_at=published,
                lookback_hours=lookback_hours,
                belfast_only=belfast_only,
            ):
                filtered_out += 1
                continue

            with Session(engine) as session:
                existing = session.exec(select(NewsIncident).where(NewsIncident.url == url)).first()
                if existing:
                    skipped += 1
                    continue

            extracted = await _featherless_extract_incident_fields(
                title=title,
                url=url,
                source=src.name,
                published_at=published,
                snippet=snippet,
            )
            resolved = resolve_news_location_to_street(
                lat=extracted.get("lat"),
                lng=extracted.get("lng"),
                street_name=extracted.get("street_name"),
                max_distance_m=200.0,
            )
            if require_street_match and not resolved.get("matched"):
                unmatched_street += 1
                continue

            incident = NewsIncident(
                source=src.name,
                url=url,
                title=title,
                published_at=published,
                location_text=extracted.get("location_text"),
                street_name=(resolved.get("street_name") if resolved.get("matched") else extracted.get("street_name")),
                street_id=resolved.get("street_id") if resolved.get("matched") else None,
                lat=resolved.get("lat") if resolved.get("matched") else extracted.get("lat"),
                lng=resolved.get("lng") if resolved.get("matched") else extracted.get("lng"),
                category=extracted.get("category"),
                severity=extracted.get("severity"),
                summary=extracted.get("summary"),
            )
            with Session(engine) as session:
                session.add(incident)
                session.commit()
                inserted += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "filtered_out": filtered_out,
        "lookback_hours": lookback_hours,
        "belfast_only": belfast_only,
        "require_street_match": require_street_match,
        "unmatched_street": unmatched_street,
        "sources": [s.name for s in sources],
    }

