"""
topics.py — semantic topic assignment.

Replaces pure keyword matching with sentence-embedding similarity:

  1. Each predefined TOPIC_AREA (sources.py) gets a centroid embedding built
     from a few prototype "description" sentences.
  2. Every incoming item is embedded once (title + summary) and compared by
     cosine similarity against every predefined centroid AND every previously
     discovered dynamic topic (persisted in digest.db, so they survive and
     accumulate members across runs just like the archive does).
  3. Items that don't clear SEMANTIC_MATCH_THRESHOLD against anything land in
     "general" and become candidates for discover_topics(), which runs
     community detection (sentence_transformers.util.community_detection)
     over the accumulated "general" pool to spin up new topics. New topics
     are labeled with extractive TF-IDF keywords — no LLM call, consistent
     with this project's free/no-API-key design — and get a color/glyph
     picked from an unused slot in the palette.

Storage notes:
  - Embeddings are only needed for items sitting in "general" (they're the
    pool discover_topics() clusters over). Once an item is classified into a
    real topic its embedding is dropped from the DB to keep digest.db small.
  - What is stored is packed as float32 bytes, base64-encoded — about 1.5KB
    per 384-dim vector instead of ~7KB for a JSON list of Python floats.
  - discover_topics() only looks at the most recent DYNAMIC_TOPIC_POOL_CAP
    "general" items (by first_seen), so clustering stays fast as the archive
    grows into the thousands.

Degradation:
  - If the embedding model can't be loaded or fails mid-run (e.g. no network
    to Hugging Face in a given Action run), assign_topics() falls back to
    the old keyword matcher from sources.py for that run instead of crashing
    the whole pipeline. No embeddings are stored for that run, so nothing
    breaks discover_topics() on subsequent runs — those items just sit in
    whatever the keyword matcher assigned them (including "general") without
    being embedding-tagged. This is a deliberate "better than crashing"
    fallback, not full parity with the semantic path.

Public entry points used by fetch.py:
    assign_topics(items, conn)   -> mutates items in place (area fields + a
                                     hidden "_embedding" key for storage)
    discover_topics(conn)        -> sweeps the "general" bucket, returns the
                                     number of new topics created
"""
import base64
import hashlib
import json
import logging
import re
from datetime import datetime, timezone

import numpy as np

import sources as cfg

log = logging.getLogger("topics")

_MODEL = None
_MODEL_FAILED = False  # sticky within a process: don't retry-and-fail per item

# Feed boilerplate that carries zero topical signal but shows up on a large
# fraction of items — Reddit's link/comments footer, MarkTechPost's syndication
# line, etc. Left in, this dilutes short titles/summaries with text that's
# identical across totally unrelated items, which drags cosine similarity down
# for genuinely related items and up for unrelated ones. Stripped before
# embedding; never touched in the stored/displayed title or summary.
_BOILERPLATE_PATTERNS = [
    re.compile(r"submitted by\s*/u/\S+", re.IGNORECASE),
    re.compile(r"\[link\]\s*\[comments\]", re.IGNORECASE),
    re.compile(r"\bthe post\b.*?\bappeared first on\b[^.]*\.?", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bsource:\s*https?://\S+", re.IGNORECASE),
]


def clean_for_embedding(title, summary):
    """Build the text handed to the encoder, with feed boilerplate stripped."""
    text = f"{title}. {summary or ''}"
    for pat in _BOILERPLATE_PATTERNS:
        text = pat.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()

# Colors handed out to newly discovered topics, in order, skipping any color
# already in use by a predefined area or an existing dynamic topic.
DYNAMIC_COLOR_PALETTE = [
    "#6C4AB6", "#2E86AB", "#C1447E", "#3A7D44", "#B8860B",
    "#4B4E6D", "#A83232", "#008080", "#946B2D", "#5A5A9E",
]

# Glyphs cycled the same way, so discovered topics look visually distinct
# from each other, not just from the predefined areas.
DYNAMIC_GLYPH_PALETTE = [
    "ti-sparkles", "ti-flask", "ti-telescope", "ti-puzzle",
    "ti-wand", "ti-compass", "ti-bulb", "ti-target-arrow",
]


class EmbeddingUnavailable(Exception):
    """Raised when the embedding model can't be loaded or used."""


# Generic research-feed/news boilerplate that plain TF-IDF doesn't reliably
# catch (it's frequent within a cluster too, not just globally, so it isn't
# penalized unless it's explicitly excluded). Layered on top of sklearn's
# built-in English stopword list.
DOMAIN_STOPWORDS = {
    "new", "paper", "papers", "study", "studies", "researcher", "researchers",
    "research", "using", "based", "via", "propose", "proposed", "proposes",
    "introduce", "introduces", "introducing", "present", "presents", "presenting",
    "result", "results", "shows", "show", "showing", "approach", "approaches",
    "method", "methods", "model", "models", "work", "works", "novel", "recent",
    "recently", "towards", "improve", "improved", "improving", "improves",
    "framework", "frameworks", "analysis", "understanding", "exploring",
    "explore", "investigate", "investigating", "case", "article", "report",
    "reports", "release", "released", "releases", "announce", "announces",
    "announcing", "today", "week", "year", "according",
}


_ALL_STOPWORDS = None


def _all_stopwords():
    global _ALL_STOPWORDS
    if _ALL_STOPWORDS is None:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        _ALL_STOPWORDS = list(ENGLISH_STOP_WORDS | DOMAIN_STOPWORDS)
    return _ALL_STOPWORDS


# ---------------------------------------------------------------------------
# embedding model + (de)serialization
# ---------------------------------------------------------------------------
def _model():
    global _MODEL, _MODEL_FAILED
    if _MODEL_FAILED:
        raise EmbeddingUnavailable("embedding model previously failed to load")
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer(cfg.EMBEDDING_MODEL)
        except Exception as ex:
            _MODEL_FAILED = True
            raise EmbeddingUnavailable(f"could not load {cfg.EMBEDDING_MODEL}: {ex}") from ex
    return _MODEL


def embed_texts(texts):
    """L2-normalized embeddings so dot product == cosine similarity."""
    try:
        vecs = _model().encode(list(texts), normalize_embeddings=True,
                                show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)
    except EmbeddingUnavailable:
        raise
    except Exception as ex:
        raise EmbeddingUnavailable(f"encoding failed: {ex}") from ex


def encode_embedding(vec):
    """np.float32 array -> compact base64 string for storage."""
    return base64.b64encode(np.asarray(vec, dtype=np.float32).tobytes()).decode("ascii")


def decode_embedding(s):
    """base64 string -> np.float32 array."""
    return np.frombuffer(base64.b64decode(s), dtype=np.float32)


# ---------------------------------------------------------------------------
# predefined + dynamic topic lookup
# ---------------------------------------------------------------------------
def _predefined_centroids():
    centroids, meta = {}, {}
    for area in cfg.TOPIC_AREAS:
        if area["id"] == "general":
            continue  # general is the fallback, never a match target
        proto = area.get("description") or [area["label"]]
        vecs = embed_texts(proto)
        c = vecs.mean(axis=0)
        centroids[area["id"]] = c / np.linalg.norm(c)
        meta[area["id"]] = area
    return centroids, meta


def load_dynamic_topics(conn):
    rows = conn.execute("SELECT * FROM dynamic_topics").fetchall()
    topics = {}
    for r in rows:
        topics[r["id"]] = {
            "label": r["label"],
            "color": r["color"],
            "glyph": r["glyph"],
            "keywords": json.loads(r["keywords"] or "[]"),
            "centroid": decode_embedding(r["centroid"]),
            "member_count": r["member_count"],
        }
    return topics


def _used_colors(dynamic_topics):
    return ({a["color"] for a in cfg.TOPIC_AREAS}
            | {t["color"] for t in dynamic_topics.values()})


def _used_glyphs(dynamic_topics):
    return ({a["glyph"] for a in cfg.TOPIC_AREAS}
            | {t["glyph"] for t in dynamic_topics.values()})


def _pick_from_palette(palette, used, kind):
    for c in palette:
        if c not in used:
            return c
    # palette exhausted — derive a stable-but-distinct value from a hash
    if kind == "color":
        h = hashlib.md5(f"color{len(used)}".encode()).hexdigest()
        return f"#{h[:6]}"
    return "ti-sparkles"  # glyph fallback: reuse the original default


def label_cluster(texts, centroid, background_vec, top_k=2, candidate_pool=15):
    """
    Labels a cluster with c-TF-IDF (BERTopic-style) candidate scoring against
    a background corpus, reranked by embedding similarity to the cluster
    centroid. Plain within-cluster TF-IDF tends to keep generic research-feed
    words ("new", "study", "using") because they're frequent *inside* the
    cluster too — scoring against the whole archive's term frequencies
    instead correctly treats them as common everywhere and downweights them.
    The embedding rerank then favors whichever surviving candidates actually
    sound like the cluster's semantic center, using the same encoder that's
    already loaded for clustering (no extra cost).
    """
    if background_vec is not None:
        try:
            counts = background_vec.transform([" ".join(texts)])
            tf = counts.toarray().ravel()
            scores = tf * background_vec.idf_
            terms = background_vec.get_feature_names_out()
        except Exception:
            terms, scores = _local_tfidf(texts)
    else:
        terms, scores = _local_tfidf(texts)  # cold start: no background yet

    if len(terms) == 0:
        return "Emerging topic", []

    order = scores.argsort()[::-1]
    candidates = [terms[i] for i in order[:candidate_pool * 3] if scores[i] > 0]
    # drop candidates containing a bare numeric word ("11", "2024") — those
    # are almost always stray indices/years, not topic labels. Keep
    # alphanumeric domain terms like "h100", "gpt4", "b200" (digits, but not
    # a standalone numeric word) since those are legitimate label material.
    candidates = [c for c in candidates
                  if not any(w.strip("v.").isdigit() for w in c.split())]
    candidates = candidates[:candidate_pool]
    if not candidates:
        return "Emerging topic", []

    try:
        cand_embs = embed_texts(candidates)
        sims = cand_embs @ centroid
        candidates = [c for c, _ in sorted(zip(candidates, sims), key=lambda x: -x[1])]
    except EmbeddingUnavailable:
        pass  # fall back to plain frequency order

    chosen, chosen_words = [], set()
    for term in candidates:
        words = set(term.split())
        if words & chosen_words:  # skip terms that share a word with one we kept
            continue
        chosen.append(term)
        chosen_words |= words
        if len(chosen) == top_k:
            break

    label = " & ".join(t.title() for t in chosen) if chosen else "Emerging topic"
    return label, candidates[:10]


def _local_tfidf(texts):
    """Fallback scoring if no background corpus is available yet (cold-start archive)."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    try:
        vec = TfidfVectorizer(max_features=3000, ngram_range=(1, 2),
                               stop_words=_all_stopwords(), min_df=1)
        X = vec.fit_transform(texts)
    except ValueError:
        return [], np.array([])
    scores = np.asarray(X.sum(axis=0)).ravel()
    return vec.get_feature_names_out(), scores


def background_vectorizer(conn, sample_size=3000):
    """
    Fits IDF weights over a broad, recent slice of the whole archive (every
    area, not just "general") once per discover_topics() run. Reused across
    every cluster labeled in that run — this is what lets label_cluster tell
    "distinctive to this cluster" apart from "common everywhere".
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    rows = conn.execute(
        "SELECT title, summary FROM items ORDER BY first_seen DESC LIMIT ?",
        (sample_size,),
    ).fetchall()
    if len(rows) < 50:
        return None  # archive too small yet for a meaningful background
    texts = [clean_for_embedding(r["title"], r["summary"]) for r in rows]
    vec = TfidfVectorizer(max_features=6000, ngram_range=(1, 2),
                           stop_words=_all_stopwords(), min_df=2)
    try:
        vec.fit(texts)
    except ValueError:
        return None
    return vec


# ---------------------------------------------------------------------------
# keyword fallback (used only if the embedding model is unavailable)
# ---------------------------------------------------------------------------
def _keyword_assign(title, summary):
    hay = (title + " " + summary).lower()
    for area in cfg.TOPIC_AREAS:
        for kw in area.get("keywords", []):
            if kw in hay:
                return area
    return cfg.TOPIC_AREAS[-1]  # general


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def assign_topics(items, conn):
    """
    Embeds all items once and assigns each to the best-matching predefined
    area or dynamic topic (falls back to "general"). Mutates each item dict
    in place with area/area_label/area_color/area_glyph and "_embedding"
    (only set for items landing in "general" — anything already classified
    doesn't need its embedding kept around).

    Degrades to keyword matching (no embeddings stored) if the model can't
    be loaded or fails on this batch, instead of crashing the whole run.
    """
    if not items:
        return items

    general = next(a for a in cfg.TOPIC_AREAS if a["id"] == "general")
    texts = [clean_for_embedding(it["title"], it.get("raw_summary") or it.get("summary"))
             for it in items]

    try:
        embeddings = embed_texts(texts)
        pre_centroids, pre_meta = _predefined_centroids()
        dyn_topics = load_dynamic_topics(conn)
    except EmbeddingUnavailable as ex:
        log.warning("Semantic classification unavailable (%s); "
                     "falling back to keyword matching for this run.", ex)
        for it, text in zip(items, texts):
            title = it["title"]
            summary = it.get("raw_summary") or it.get("summary") or ""
            a = _keyword_assign(title, summary)
            it.update(area=a["id"], area_label=a["label"],
                      area_color=a["color"], area_glyph=a["glyph"])
            it["_embedding"] = None
        return items

    pre_ids = list(pre_centroids.keys())
    pre_mat = np.stack([pre_centroids[i] for i in pre_ids]) if pre_ids else None
    dyn_ids = list(dyn_topics.keys())
    dyn_mat = np.stack([dyn_topics[i]["centroid"] for i in dyn_ids]) if dyn_ids else None

    for it, emb in zip(items, embeddings):
        best_id, best_score, best_kind = None, -1.0, None
        if pre_mat is not None:
            sims = pre_mat @ emb
            j = int(sims.argmax())
            if sims[j] > best_score:
                best_id, best_score, best_kind = pre_ids[j], float(sims[j]), "predefined"
        if dyn_mat is not None:
            sims = dyn_mat @ emb
            j = int(sims.argmax())
            if sims[j] > best_score:
                best_id, best_score, best_kind = dyn_ids[j], float(sims[j]), "dynamic"

        matched = best_id is not None and best_score >= cfg.SEMANTIC_MATCH_THRESHOLD
        if matched:
            if best_kind == "predefined":
                a = pre_meta[best_id]
                it.update(area=a["id"], area_label=a["label"],
                          area_color=a["color"], area_glyph=a["glyph"])
            else:
                d = dyn_topics[best_id]
                it.update(area=best_id, area_label=d["label"],
                          area_color=d["color"], area_glyph=d["glyph"])
            it["_embedding"] = None  # already classified, no need to keep it
        else:
            it.update(area=general["id"], area_label=general["label"],
                       area_color=general["color"], area_glyph=general["glyph"])
            it["_embedding"] = encode_embedding(emb)  # kept for future clustering

    return items


def backfill_general_embeddings(conn, limit=None):
    """
    Legacy/self-healing step: any "general" item whose embedding is NULL
    either predates this module (inserted by the old keyword matcher before
    this upgrade) or was classified during a run where the model was
    temporarily unavailable (assign_topics()'s fallback path). Either way,
    discover_topics() can never see it — its WHERE clause requires a
    non-NULL embedding. This re-embeds any such backlog so it becomes
    eligible for clustering. Idempotent: once caught up, it's a no-op query
    on every subsequent run, so it's safe to call unconditionally.
    """
    query = ("SELECT id, title, summary FROM items "
             "WHERE area='general' AND embedding IS NULL")
    params = ()
    if limit:
        query += " LIMIT ?"
        params = (limit,)
    rows = conn.execute(query, params).fetchall()
    if not rows:
        return 0

    texts = [clean_for_embedding(r["title"], r["summary"]) for r in rows]
    try:
        embeddings = embed_texts(texts)
    except EmbeddingUnavailable as ex:
        log.warning("Skipping embedding backfill: %s", ex)
        return 0

    conn.executemany(
        "UPDATE items SET embedding=? WHERE id=?",
        [(encode_embedding(e), r["id"]) for e, r in zip(embeddings, rows)],
    )
    conn.commit()
    return len(rows)


def discover_topics(conn):
    """
    Community detection over the most recent DYNAMIC_TOPIC_POOL_CAP archived
    items still sitting in "general". Creates new dynamic topics (or merges
    into existing ones if a cluster's centroid is close enough to one already
    discovered), reassigns member items' area fields, clears their now-unused
    embeddings, and returns the number of new topics created.
    """
    try:
        from sentence_transformers import util
    except Exception as ex:
        log.warning("Skipping topic discovery: sentence-transformers unavailable (%s)", ex)
        return 0

    rows = conn.execute(
        "SELECT id, title, summary, embedding FROM items "
        "WHERE area='general' AND embedding IS NOT NULL "
        "ORDER BY first_seen DESC LIMIT ?",
        (cfg.DYNAMIC_TOPIC_POOL_CAP,),
    ).fetchall()
    if len(rows) < cfg.DYNAMIC_TOPIC_MIN_CLUSTER:
        return 0

    ids = [r["id"] for r in rows]
    texts = [clean_for_embedding(r["title"], r["summary"]) for r in rows]
    embs = np.array([decode_embedding(r["embedding"]) for r in rows], dtype=np.float32)

    clusters = util.community_detection(
        embs,
        threshold=cfg.DYNAMIC_TOPIC_THRESHOLD,
        min_community_size=cfg.DYNAMIC_TOPIC_MIN_CLUSTER,
    )
    if not clusters:
        return 0

    existing = load_dynamic_topics(conn)
    existing_ids = list(existing.keys())
    existing_mat = (np.stack([existing[i]["centroid"] for i in existing_ids])
                    if existing_ids else None)
    used_colors = _used_colors(existing)
    used_glyphs = _used_glyphs(existing)
    bg_vec = background_vectorizer(conn)  # built once, reused for every cluster below

    created = 0
    now = datetime.now(timezone.utc).isoformat()

    for member_idxs in clusters:
        member_ids = [ids[i] for i in member_idxs]
        cluster_embs = embs[member_idxs]
        centroid = cluster_embs.mean(axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        cluster_texts = [texts[i] for i in member_idxs]

        target_id = None
        if existing_mat is not None:
            sims = existing_mat @ centroid
            j = int(sims.argmax())
            if sims[j] >= cfg.DYNAMIC_TOPIC_MERGE_THRESHOLD:
                target_id = existing_ids[j]

        if target_id:
            merged_centroid = (existing[target_id]["centroid"] + centroid) / 2
            merged_centroid = merged_centroid / np.linalg.norm(merged_centroid)
            conn.execute(
                "UPDATE dynamic_topics SET centroid=?, member_count=member_count+?, "
                "updated=? WHERE id=?",
                (encode_embedding(merged_centroid), len(member_ids), now, target_id),
            )
            area_id = target_id
            area_label = existing[target_id]["label"]
            area_color = existing[target_id]["color"]
            area_glyph = existing[target_id]["glyph"]
        else:
            label, keywords = label_cluster(cluster_texts, centroid, bg_vec)
            topic_id = f"dyn_{hashlib.md5(label.encode()).hexdigest()[:8]}"
            color = _pick_from_palette(DYNAMIC_COLOR_PALETTE, used_colors, "color")
            glyph = _pick_from_palette(DYNAMIC_GLYPH_PALETTE, used_glyphs, "glyph")
            used_colors.add(color)
            used_glyphs.add(glyph)
            conn.execute(
                "INSERT INTO dynamic_topics "
                "(id,label,keywords,color,glyph,centroid,member_count,created,updated) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (topic_id, label, json.dumps(keywords), color, glyph,
                 encode_embedding(centroid), len(member_ids), now, now),
            )
            area_id, area_label, area_color, area_glyph = topic_id, label, color, glyph
            created += 1

        # reassign members and drop their embeddings — no longer needed once
        # an item has left the "general" clustering pool
        conn.executemany(
            "UPDATE items SET area=?, area_label=?, area_color=?, area_glyph=?, "
            "embedding=NULL WHERE id=?",
            [(area_id, area_label, area_color, area_glyph, iid) for iid in member_ids],
        )

    conn.commit()
    return created
