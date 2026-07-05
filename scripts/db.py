"""
db.py — the persistent archive. One SQLite file (digest.db) lives in the repo;
the daily job opens it, inserts new items (ignoring ones already seen), prunes
anything older than ARCHIVE_YEARS, and the builder reads from it.

SQLite is a single file, needs no server, and is committed back to the repo by
the GitHub Action so the archive survives between runs and grows over time.
"""

import sqlite3
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

import sources as cfg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "digest.db"


def _key(link, title):
    norm = re.sub(r"\W+", "", (title or "").lower())[:60]
    return hashlib.md5((link + norm).encode()).hexdigest()


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            summary      TEXT,
            link         TEXT NOT NULL,
            source       TEXT,
            source_kind  TEXT,
            published    TEXT,
            published_ts REAL,
            area         TEXT,
            area_label   TEXT,
            area_color   TEXT,
            area_glyph   TEXT,
            is_hot       INTEGER,
            orgs         TEXT,
            image        TEXT,
            first_seen   TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON items(published_ts DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_area ON items(area)")

    # migration: older archives won't have this column yet
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(items)")}
    if "embedding" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN embedding TEXT")

    # dynamic topics discovered by topics.discover_topics(), persisted like
    # everything else here so they survive and accumulate across runs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_topics (
            id            TEXT PRIMARY KEY,
            label         TEXT NOT NULL,
            keywords      TEXT,
            color         TEXT,
            glyph         TEXT,
            centroid      TEXT NOT NULL,
            member_count  INTEGER DEFAULT 0,
            created       TEXT,
            updated       TEXT
        )
    """)
    conn.commit()
    return conn


def upsert_many(conn, items):
    """Insert new items; skip ones already in the archive. Returns count added."""
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for it in items:
        iid = _key(it["link"], it["title"])
        exists = conn.execute("SELECT 1 FROM items WHERE id=?", (iid,)).fetchone()
        if exists:
            continue
        emb = it.get("_embedding")
        conn.execute("""
            INSERT INTO items (id,title,summary,link,source,source_kind,published,
                published_ts,area,area_label,area_color,area_glyph,is_hot,orgs,image,
                embedding,first_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            iid, it["title"], it["summary"], it["link"], it["source"],
            it["source_kind"], it["published"], it["published_ts"], it["area"],
            it["area_label"], it["area_color"], it["area_glyph"],
            1 if it["is_hot"] else 0, json.dumps(it["orgs"]), it.get("image"),
            json.dumps(emb) if emb is not None else None, now,
        ))
        added += 1
    conn.commit()
    return added


def prune(conn):
    """Delete items older than ARCHIVE_YEARS. Returns count removed."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=365 * cfg.ARCHIVE_YEARS)).timestamp()
    cur = conn.execute("DELETE FROM items WHERE published_ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


def _row_to_item(r):
    return {
        "id": r["id"], "title": r["title"], "summary": r["summary"],
        "link": r["link"], "source": r["source"], "source_kind": r["source_kind"],
        "published": r["published"], "published_ts": r["published_ts"],
        "area": r["area"], "area_label": r["area_label"],
        "area_color": r["area_color"], "area_glyph": r["area_glyph"],
        "is_hot": bool(r["is_hot"]), "orgs": json.loads(r["orgs"] or "[]"),
        "image": r["image"],
    }


def recent_items(conn, days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    rows = conn.execute(
        "SELECT * FROM items WHERE published_ts >= ? ORDER BY published_ts DESC",
        (cutoff,)).fetchall()
    return [_row_to_item(r) for r in rows]


def all_items(conn):
    rows = conn.execute(
        "SELECT * FROM items ORDER BY published_ts DESC").fetchall()
    return [_row_to_item(r) for r in rows]


def month_counts(conn):
    """Return [(YYYY-MM, count), ...] newest first, for the archive timeline."""
    rows = conn.execute("""
        SELECT strftime('%Y-%m', datetime(published_ts,'unixepoch')) AS ym,
               COUNT(*) AS n
        FROM items WHERE published_ts > 0
        GROUP BY ym ORDER BY ym DESC
    """).fetchall()
    return [(r["ym"], r["n"]) for r in rows]


def stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    oldest = conn.execute(
        "SELECT MIN(published_ts) FROM items WHERE published_ts>0").fetchone()[0]
    return {"total": total, "oldest_ts": oldest}
