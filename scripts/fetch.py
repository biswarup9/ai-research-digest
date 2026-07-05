"""
fetch.py — crawls every source, normalizes to one item shape, dedupes,
tags by research area, flags hot items, sorts by recency, writes data.json.

Run:  python3 fetch.py
Out:  site/data.json   (consumed by build.py, never touches the network)
"""

import re
import json
import time
import hashlib
import html
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import feedparser
import trafilatura

from bs4 import BeautifulSoup

import sources as cfg
from summarize import summarize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / ".cache"
CACHE.mkdir(exist_ok=True)
OUT = ROOT / "site" / "data.json"

UA = "ai-digest/1.0 (personal feed reader; +https://github.com)"
HEADERS = {"User-Agent": UA}
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=cfg.FETCH_WINDOW_DAYS)

# track which feeds were alive this run, for the report at the end
REPORT = {"ok": [], "empty": [], "failed": []}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def clean(text, limit=320):
    """Strip HTML tags/entities from a summary and trim to a sane length."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # drop tags
    text = html.unescape(text)                     # &amp; -> &
    text = re.sub(r"\s+", " ", text).strip()       # collapse whitespace
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def parse_date(entry):
    """Return a tz-aware datetime from a feed entry, or None."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def extract_image(entry):
    """Best-effort og:image-style thumbnail from a feed entry. May be None."""
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image") and link.get("href"):
            return link["href"]
    # some feeds embed an <img> in the summary html
    m = re.search(r'<img[^>]+src="([^"]+)"', entry.get("summary", ""))
    if m:
        return m.group(1)
    return None


def scrape_latest_articles(site_url, source, kind):
    """
    Generic website scraper used when RSS fails.
    """
    articles = []

    try:
        r = requests.get(site_url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")

        urls = []

        for a in soup.find_all("a", href=True):
            href = urllib.parse.urljoin(site_url, a["href"])

            if href.startswith(site_url):

                if any(x in href.lower() for x in [
                    "/blog",
                    "/news",
                    "/research",
                    "/article",
                    "/post",
                ]):
                    urls.append(href)

        urls = list(dict.fromkeys(urls))

        for url in urls[:20]:

            downloaded = trafilatura.fetch_url(url)

            if not downloaded:
                continue

            result = trafilatura.extract(
                downloaded,
                output_format="json",
                with_metadata=True,
            )

            if not result:
                continue

            data = json.loads(result)

            published = NOW

            if data.get("date"):
                try:
                    published = datetime.fromisoformat(
                        data["date"].replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            item = make_item(
                data.get("title", ""),
                data.get("text", ""),
                url,
                source,
                kind,
                published,
            )

            if item:
                articles.append(item)

    except Exception as ex:
        REPORT["failed"].append(f"{source} Scraper: {ex}")

    return articles


def detect_hot(title):
    t = title.lower()
    return any(sig in t for sig in cfg.HOT_SIGNALS)


def detect_orgs(title, summary):
    hay = (title + " " + summary).lower()
    found = []
    for org in cfg.WATCHED_ORGS:
        # word-boundary match so "cohere" doesn't fire inside "coherence"
        if re.search(r"\b" + re.escape(org) + r"\b", hay):
            found.append(org)
    return found


def make_item(title, summary, link, source, kind, published, image=None):
    title = clean(title, 200)
    raw = clean(summary, 600)
    if not title or not link:
        return None
    # area/area_label/area_color/area_glyph are filled in later, in bulk, by
    # topics.assign_topics() — it's far more efficient to embed everything in
    # one batch than to embed item-by-item as they stream in from each source.
    return {
        "title": title,
        "summary": summarize(raw, max_sentences=2, max_chars=260),
        "raw_summary": raw,  # kept only for embedding text; not persisted
        "link": link,
        "source": source,
        "source_kind": kind,
        "published": published.isoformat() if published else None,
        "published_ts": published.timestamp() if published else 0,
        "is_hot": detect_hot(title),
        "orgs": detect_orgs(title, raw),
        "image": image,  # captured now; builder uses it only if hybrid is on
    }


# ---------------------------------------------------------------------------
# fetchers
# ---------------------------------------------------------------------------
def fetch_arxiv():
    items = []
    base = "http://export.arxiv.org/api/query"
    for cat in cfg.ARXIV_CATEGORIES:
        params = {
            "search_query": f"cat:{cat}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": cfg.ARXIV_MAX_PER_CATEGORY,
        }
        url = base + "?" + urllib.parse.urlencode(params)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            feed = feedparser.parse(r.content)
            n = 0
            for e in feed.entries:
                pub = parse_date(e)
                if pub and pub < CUTOFF:
                    continue
                it = make_item(
                    e.get("title", ""), e.get("summary", ""),
                    e.get("link", ""), f"arXiv {cat}", "paper", pub,
                )
                if it:
                    items.append(it)
                    n += 1
            REPORT["ok"].append(f"arXiv {cat} ({n})")
        except Exception as ex:
            REPORT["failed"].append(f"arXiv {cat}: {ex}")
        time.sleep(3)  # arXiv asks for ~3s between calls
    return items


def fetch_rss():
    items = []
    for source in cfg.RSS_FEEDS:
        label = source["label"]
        url = source["rss"]
        site_url = source["site"]
        kind = source["kind"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"RSS failed for {label}. Using scraper.")

                items.extend(
                    scrape_latest_articles(
                        site_url,
                        label,
                        kind,
                    )
                )
                continue
            feed = feedparser.parse(r.content)
            if not feed.entries:
                print(f"No RSS entries for {label}. Using scraper.")
                items.extend(
                    scrape_latest_articles(
                        site_url,
                        label,
                        kind,
                    )
                )
                continue
            n = 0
            for e in feed.entries[:30]:
                pub = parse_date(e)
                if pub and pub < CUTOFF:
                    continue
                it = make_item(
                    e.get("title", ""),
                    e.get("summary", ""),
                    e.get("link", ""),
                    label,
                    kind,
                    pub,
                    image=extract_image(e),
                )
                if it:
                    items.append(it)
                    n += 1
            REPORT["ok"].append(f"{label} ({n})")

        except Exception as ex:
            print(f"{label} RSS Exception. Falling back to scraper.")
            items.extend(
                scrape_latest_articles(
                    site_url,
                    label,
                    kind,
                )
            )
    return items


def fetch_reddit():
    url = "https://www.reddit.com/r/singularity/top/.rss?sort=top&t=day"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            REPORT["failed"].append(f"r/singularity: HTTP {r.status_code}")
            return items
        
        feed = feedparser.parse(r.content)
        entries = sorted(
            feed.entries,
            key=lambda x: parse_date(x) or NOW,
            reverse=True,
        )

        for e in entries[:30]:
            pub = parse_date(e)
            if pub and pub < CUTOFF:
                continue
            it = make_item(
                e.get("title", ""), e.get("summary", ""),
                e.get("link", ""), "r/singularity", "community", pub,
                image=extract_image(e),
            )
            if it:
                items.append(it)
        REPORT["ok"].append(f"r/singularity ({len(items)})")
    except Exception as ex:
        REPORT["failed"].append(f"r/singularity: {ex}")
    return items


def resolve_youtube_channel_id(handle_url):
    """Fetch channel page once, regex the UC id, cache it forever."""
    cache_file = CACHE / "yt_channel_id.txt"
    if cache_file.exists():
        cid = cache_file.read_text().strip()
        if cid.startswith("UC"):
            return cid
    try:
        r = requests.get(handle_url, headers=HEADERS, timeout=30)
        m = (re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
             or re.search(r'channel_id=(UC[\w-]{22})', r.text)
             or re.search(r'"externalId":"(UC[\w-]{22})"', r.text))
        if m:
            cid = m.group(1)
            cache_file.write_text(cid)
            return cid
    except Exception:
        pass
    return None


def fetch_youtube():
    items = []
    cid = resolve_youtube_channel_id("https://www.youtube.com/@aiexplained-official")
    if not cid:
        REPORT["failed"].append("AI Explained: could not resolve channel id")
        return items
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        feed = feedparser.parse(r.content)
        for e in feed.entries[:15]:
            pub = parse_date(e)
            if pub and pub < CUTOFF:
                continue
            summary = e.get("summary", "") or (
                e.get("media_description", "") if hasattr(e, "media_description") else "")
            it = make_item(
                e.get("title", ""), summary, e.get("link", ""),
                "AI Explained", "video", pub,
            )
            if it:
                items.append(it)
        REPORT["ok"].append(f"AI Explained ({len(items)})")
    except Exception as ex:
        REPORT["failed"].append(f"AI Explained: {ex}")
    return items


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------
def dedupe(items):
    seen, out = set(), []
    for it in items:
        norm_title = re.sub(r"\W+", "", it["title"].lower())[:60]
        key = hashlib.md5((it["link"] + norm_title).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def main():
    import db
    import topics

    print("Fetching arXiv…")
    items = fetch_arxiv()
    print("Fetching RSS feeds…")
    items += fetch_rss()
    print("Fetching Reddit…")
    items += fetch_reddit()
    print("Fetching YouTube…")
    items += fetch_youtube()

    print(f"\nRaw items this run: {len(items)}")
    items = dedupe(items)
    print(f"After in-run dedupe: {len(items)}")

    conn = db.connect()

    print("Embedding + classifying topics…")
    topics.assign_topics(items, conn)  # sets area fields + item["_embedding"]
    for it in items:
        it.pop("raw_summary", None)  # was only needed for embedding text

    # persist into the archive (skips items already seen in prior runs)
    added = db.upsert_many(conn, items)
    removed = db.prune(conn)

    print("Backfilling embeddings for legacy/un-embedded general items…")
    backfilled = topics.backfill_general_embeddings(conn)

    print("Sweeping for emergent topics…")
    discovered = topics.discover_topics(conn)  # community detection over "general"

    st = db.stats(conn)
    conn.close()

    # report
    print("\n--- FEED REPORT ---")
    print(f"OK ({len(REPORT['ok'])}):")
    for x in REPORT["ok"]:
        print("   ", x)
    if REPORT["empty"]:
        print(f"EMPTY ({len(REPORT['empty'])}):", ", ".join(REPORT["empty"]))
    if REPORT["failed"]:
        print(f"FAILED ({len(REPORT['failed'])}):")
        for x in REPORT["failed"]:
            print("   ", x)
    print(f"\nArchive: +{added} new, -{removed} pruned, {st['total']} total items")
    print(f"Legacy items backfilled with embeddings: {backfilled}")
    print(f"New topics discovered this run: {discovered}")


if __name__ == "__main__":
    main()
