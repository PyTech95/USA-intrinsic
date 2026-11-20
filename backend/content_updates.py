"""One-time content updates that ship with the code.

The live database is seeded only once (see seed() in server.py), so content that
must go live with a release — for example an article supplied by the client — is
applied here on startup, exactly once per update key.

Rules:
- An update is recorded in the `content_updates` collection before it is applied,
  so it never runs twice (also safe with several server workers starting together).
- Existing content is never overwritten: if an article with the same URL slug or
  title is already in the database, it is left exactly as the admin has it.
- If an admin later edits, unpublishes or deletes the article, it stays that way.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from scripts.seed_it_partner_article import ARTICLE as IT_PARTNER_ARTICLE
from scripts.seed_cybersecurity_article import ARTICLE as CYBERSECURITY_ARTICLE

logger = logging.getLogger(__name__)

# (update key, article document). Add new entries at the end; never reuse a key.
ARTICLE_UPDATES = [
    ("article-choosing-it-services-partner-v1", IT_PARTNER_ARTICLE),
    ("article-cybersecurity-managed-it-v1", CYBERSECURITY_ARTICLE),
]


async def _insert_article(db, article: dict) -> bool:
    """Insert the article unless one with the same slug or title already exists."""
    existing = await db.blogs.find_one({"$or": [{"slug": article["slug"]}, {"title": article["title"]}]})
    if existing:
        return False
    last = await db.blogs.find_one({}, {"_id": 0, "order": 1}, sort=[("order", -1)])
    now = datetime.now(timezone.utc)
    doc = {
        **article,
        "id": str(uuid.uuid4()),
        "order": (last["order"] + 1) if last and isinstance(last.get("order"), int) else 0,
        "date": now.strftime("%d %b %Y"),          # publication date = the day it goes live
        "created_at": now.isoformat(),
    }
    await db.blogs.insert_one(doc)
    return True


async def apply_content_updates(db) -> list[str]:
    """Apply any pending updates. Returns the keys applied in this run."""
    await db.content_updates.create_index("key", unique=True)
    applied = []
    for key, article in ARTICLE_UPDATES:
        try:
            await db.content_updates.insert_one({"key": key, "applied_at": datetime.now(timezone.utc).isoformat()})
        except DuplicateKeyError:
            continue                                # already applied (or another worker is applying it)
        try:
            inserted = await _insert_article(db, article)
        except Exception:
            await db.content_updates.delete_one({"key": key})   # let the next start retry
            raise
        await db.content_updates.update_one({"key": key}, {"$set": {"inserted": inserted}})
        logger.info("Content update %s applied (%s)", key, "article published" if inserted else "article already present")
        applied.append(key)
    return applied
