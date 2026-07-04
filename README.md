# AI digest

A free, self-refreshing AI research and news feed. Pulls arXiv, company lab
blogs, news, newsletters, Reddit, and YouTube into a magazine-style page with a
growing searchable archive. Runs entirely on free GitHub infrastructure: no
server, no API keys, no cost.

## What it does

- **Today view** — a magazine layout: one hero story, then research areas
  (Graphics, Cognition, Systems, Quantum, Models, and more), each with flip
  cards. Newest items, current window only.
- **Archive view** — every item ever collected (up to 5 years), grouped by
  date, with a month timeline and fuzzy ranked search (MiniSearch).
- **Refreshes twice daily** on its own. Your iPad just reloads the page.

## How it works

```
GitHub Actions cron
   -> fetch.py     pulls 26 sources, summarizes, tags by research area
   -> digest.db    SQLite archive: appends new items, prunes >5yr, committed back
   -> build.py     renders index.html (Today + Archive) + per-area JSON API
   -> GitHub Pages serves it at your URL
```

The archive (`digest.db`) is committed back to the repo each run, so older
items persist and accumulate instead of disappearing.

## One-time setup (about 10 minutes)

1. **Create a GitHub repo** (free account is fine). Name it e.g. `ai-digest`.
2. **Upload these files** — drag the whole folder into the repo, or:
   ```
   git init
   git add .
   git commit -m "Initial AI digest"
   git remote add origin https://github.com/YOURNAME/ai-digest.git
   git push -u origin main
   ```
3. **Enable GitHub Pages**: repo Settings -> Pages -> Source: "GitHub Actions".
4. **Enable Actions write access**: Settings -> Actions -> General ->
   Workflow permissions -> "Read and write permissions" -> Save.
   (This lets the job commit the updated archive back.)
5. **Run it once**: Actions tab -> "Refresh AI digest" -> "Run workflow".
   First run resolves the YouTube channel id and seeds the archive.
6. **Open your site**: `https://YOURNAME.github.io/ai-digest/`
   Add it to your iPad home screen (Share -> Add to Home Screen) for an
   app-like icon.

That's it. It now refreshes twice a day automatically.

## Tuning your feed

Everything is in `scripts/sources.py`:

- `ARXIV_CATEGORIES` — add/remove arXiv categories.
- `RSS_FEEDS` — add/remove blogs, news, newsletters. Dead feeds are reported
  in the Actions log and simply skipped.
- `TOPIC_AREAS` — the research-area buckets and their keywords. Add a keyword
  to sharpen an area, reorder to change matching priority (first match wins).
- `HOT_SIGNALS` / `WATCHED_ORGS` — what flags an item "hot" / tags an org.
- `ARCHIVE_YEARS`, `TODAY_WINDOW_DAYS`, `FETCH_WINDOW_DAYS` — retention and
  window sizes.

Edit, commit, push. The next run uses your changes.

## Running locally (optional)

```
pip install -r requirements.txt
python scripts/fetch.py     # pulls sources into digest.db
python scripts/build.py     # writes site/index.html
open site/index.html        # view it
```

## Files

```
scripts/sources.py    config: sources, areas, settings  (edit this to tune)
scripts/fetch.py      crawls sources, summarizes, ingests into the archive
scripts/summarize.py  free extractive summarizer (no LLM)
scripts/db.py         SQLite archive layer
scripts/build.py      renders the page + API from the archive
.github/workflows/refresh.yml   the daily cron + deploy
digest.db             the archive (created on first run, grows over time)
site/                 the published site
```

## Notes

- **Search** is keyword-based with fuzzy matching, prefix, and relevance
  ranking (MiniSearch, client-side). Not semantic. See the chat history for the
  build-time-embeddings upgrade path if you ever want semantic search.
- **Summaries** are extractive (best sentences from the abstract). To get
  plain-language LLM summaries later, add an API key and a summary step in
  `fetch.py` — the rest of the system is unchanged.
- **Images** use generated cover art keyed to research area. Real `og:image`
  is already captured per item, so flipping to hybrid (real image when present,
  else cover art) is a small builder change.
