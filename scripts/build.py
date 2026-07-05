"""
build.py — reads the SQLite archive and renders a self-contained site/index.html
with two views (Today + Archive), client-side MiniSearch over the full archive,
and per-area JSON API files.

No network at runtime: archive data is injected into the page. The Today view
shows the recent window; the Archive view holds everything with month grouping,
fuzzy/ranked search, and pagination.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sources as cfg
import db
import topics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "site" / "index.html"


def _mentions_hot_keyword(title):
    t = (title or "").lower()
    return any(sig in t for sig in cfg.HOT_SIGNALS)


def _embed_for_heroes(items):
    """
    Best-effort embeddings for hero scoring, computed fresh at build time over
    just the current window (never persisted — this is unrelated to the
    "general" bucket embeddings topics.py stores for clustering). Returns
    None if the model can't be loaded, so score_heroes() can fall back
    gracefully instead of crashing the build.
    """
    if not items:
        return {}
    try:
        texts = [topics.clean_for_embedding(it["title"], it.get("summary")) for it in items]
        embs = topics.embed_texts(texts)
        return {it["id"]: emb for it, emb in zip(items, embs)}
    except topics.EmbeddingUnavailable:
        return None


def score_heroes(items, id_to_emb, top_n=5, sim_threshold=0.5, dedupe_threshold=0.75):
    """
    Rank items for the hero carousel. The dominant signal is cross-source
    corroboration: how many OTHER items in the same window are independently
    covering something very similar. Several different sources (an arXiv
    paper, a Reddit post, a blog writeup...) all reporting near-identical
    stories in the same window is much stronger, wording-independent evidence
    of real importance than any keyword match. A watched-org mention and the
    old HOT_SIGNALS keyword list still contribute as smaller boosts, and
    recency breaks remaining ties.

    Falls back to just the newest items (already sorted that way) if
    embeddings aren't available — same "degrade, don't crash" approach used
    throughout this project.

    Deduplicates: if two items are near-identical (same story, different
    source), only the higher-scoring one is kept, so the carousel doesn't
    show the same story twice.
    """
    if not items:
        return []
    if id_to_emb is None:
        return items[:top_n]

    ids = [it["id"] for it in items]
    embs = np.array([id_to_emb[i] for i in ids])
    sims = embs @ embs.T
    n = len(items)

    newest_ts = max((it["published_ts"] or 0) for it in items)
    oldest_ts = min((it["published_ts"] or 0) for it in items)
    span = max(newest_ts - oldest_ts, 1)

    scores = []
    for i, it in enumerate(items):
        corroboration = int((sims[i] >= sim_threshold).sum()) - 1  # exclude self
        org_boost = 1.0 if it.get("orgs") else 0.0
        keyword_boost = 0.5 if _mentions_hot_keyword(it["title"]) else 0.0
        recency = ((it["published_ts"] or 0) - oldest_ts) / span
        scores.append(3.0 * corroboration + org_boost + keyword_boost + 0.3 * recency)

    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    chosen, chosen_idx = [], []
    for i in order:
        if any(sims[i][j] >= dedupe_threshold for j in chosen_idx):
            continue  # near-duplicate of an already-chosen hero — skip
        chosen.append(items[i])
        chosen_idx.append(i)
        if len(chosen) >= top_n:
            break
    return chosen


def build():
    conn = db.connect()
    recent = db.recent_items(conn, cfg.TODAY_WINDOW_DAYS)
    weekly = db.recent_items(conn, cfg.WEEKLY_WINDOW_DAYS)
    archive = db.all_items(conn)
    months = db.month_counts(conn)
    st = db.stats(conn)
    dynamic_topics = conn.execute(
        "SELECT id, label, color, glyph FROM dynamic_topics ORDER BY member_count DESC"
    ).fetchall()
    conn.close()

    # Predefined areas (config order) first, then discovered dynamic topics,
    # "general" last. Shared by Today, Weekly, and (client-side) Favorites so
    # all three group and order areas identically regardless of which items
    # each one actually contains.
    ordered_areas = ([a for a in cfg.TOPIC_AREAS if a["id"] != "general"]
                      + [{"id": r["id"], "label": r["label"], "color": r["color"],
                          "glyph": r["glyph"]} for r in dynamic_topics]
                      + [next(a for a in cfg.TOPIC_AREAS if a["id"] == "general")])

    def group_by_area(items):
        by_area = {}
        for area in ordered_areas:
            members = [i for i in items if i["area"] == area["id"]]
            if members:
                by_area[area["id"]] = {
                    "label": area["label"], "color": area["color"],
                    "glyph": area["glyph"], "items": members,
                }
        return by_area

    by_area = group_by_area(recent)
    by_area_weekly = group_by_area(weekly)
    # weekly is a superset of recent (WEEKLY_WINDOW_DAYS > TODAY_WINDOW_DAYS),
    # so embed it once and reuse the lookup for both hero carousels rather
    # than encoding the "recent" items twice.
    id_to_emb = _embed_for_heroes(weekly)
    heroes = score_heroes(recent, id_to_emb, top_n=5)
    heroes_week = score_heroes(weekly, id_to_emb, top_n=5)

    oldest = None
    if st["oldest_ts"]:
        oldest = datetime.fromtimestamp(st["oldest_ts"], timezone.utc).strftime("%b %Y")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today_count": len(recent),
        "weekly_count": len(weekly),
        "archive_total": st["total"],
        "oldest": oldest,
        "hero": heroes[0] if heroes else None,
        "heroes": heroes,
        "hero_week": heroes_week[0] if heroes_week else None,
        "heroes_week": heroes_week,
        "areas": by_area,
        "areas_weekly": by_area_weekly,
        # full area list (id/label/color/glyph only) in canonical order, so
        # Favorites — built client-side from whatever's been favorited,
        # which won't line up with either "areas" dict above — can group
        # and order its own sections consistently with everything else.
        "area_order": [{"id": a["id"], "label": a["label"], "color": a["color"],
                         "glyph": a["glyph"]} for a in ordered_areas],
        "archive": archive,       # full list, newest first, for archive view + search
        "months": months,         # [[YYYY-MM, count], ...]
    }

    html_out = TEMPLATE.replace("__DATA__", json.dumps(payload))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html_out)
    print(f"Wrote {OUT} ({OUT.stat().st_size//1024} KB)")

    # mini "API": per-area files + index
    api = ROOT / "site" / "api"
    api.mkdir(exist_ok=True)
    idx = {"generated_at": payload["generated_at"], "archive_total": st["total"], "areas": []}
    area_groups = {}
    for it in archive:
        area_groups.setdefault(it["area"], []).append(it)
    for aid, items in area_groups.items():
        (api / f"{aid}.json").write_text(json.dumps(
            {"label": items[0]["area_label"], "count": len(items), "items": items}, indent=2))
        idx["areas"].append({"id": aid, "label": items[0]["area_label"],
                             "count": len(items), "url": f"api/{aid}.json"})
    (api / "index.json").write_text(json.dumps(idx, indent=2))
    print(f"Wrote {len(idx['areas'])} per-area API files")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#13243a">
<title>AI digest</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/3.7.0/tabler-icons.min.css">
<script src="https://cdn.jsdelivr.net/npm/minisearch@7.1.0/dist/umd/index.min.js"></script>
<style>
:root{--bg:#f7f6f2;--surf:#fff;--surf1:#f1efe8;--surf0:#efeee8;--txt:#1f1f1d;--txt2:#5f5e5a;--txt3:#888780;--bd:#e3e1d8;--bds:#cfcdc3;--accent:#185FA5}
@media (prefers-color-scheme:dark){:root{--bg:#1b1b19;--surf:#26262a;--surf1:#222226;--surf0:#1f1f22;--txt:#e8e6dd;--txt2:#b4b2a9;--txt3:#888780;--bd:#3a3a3e;--bds:#4a4a4e;--accent:#85B7EB}}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.5}
.shell{max-width:760px;margin:0 auto;padding-bottom:60px}
.hd{position:sticky;top:0;z-index:30;background:var(--bg);padding:15px 16px 0;border-bottom:0.5px solid var(--bd)}
.hdt{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.brand{display:flex;align-items:center;gap:9px}
.logo{width:32px;height:32px;border-radius:8px;background:#185FA5;display:flex;align-items:center;justify-content:center;color:#fff;font-size:17px;position:relative;overflow:hidden}
.logo::after{content:'';position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent,transparent 6px,rgba(255,255,255,.08) 6px,rgba(255,255,255,.08) 12px)}
.bn{font-size:17px;font-weight:600;line-height:1}.bs{font-size:11px;color:var(--txt3);margin-top:2px}
.live{font-size:10px;padding:3px 9px;border-radius:20px;background:rgba(59,109,17,.12);color:#3B6D11;display:flex;align-items:center;gap:5px;font-weight:600}
@media (prefers-color-scheme:dark){.live{color:#97C459;background:rgba(151,196,89,.14)}}
.ld{width:5px;height:5px;border-radius:50%;background:currentColor;animation:pls 1.6s ease-in-out infinite}
@keyframes pls{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(1.6)}}
.tabs{display:flex;gap:2px}
.tab{flex:1;text-align:center;font-size:12px;font-weight:600;padding:10px 2px;color:var(--txt3);cursor:pointer;border-bottom:2px solid transparent;display:flex;align-items:center;justify-content:center;gap:5px;user-select:none;white-space:nowrap}
.tab.on{color:var(--txt);border-bottom-color:var(--accent)}
.view{display:none}.view.on{display:block}
.fl{padding:11px 16px;display:flex;gap:6px;overflow-x:auto;border-bottom:0.5px solid var(--bd);scrollbar-width:none}
.fl::-webkit-scrollbar{display:none}
.ch{font-size:12px;padding:6px 12px;border-radius:20px;border:0.5px solid var(--bd);background:var(--surf);color:var(--txt2);cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:5px;user-select:none}
.ch.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}.ch .dot{width:7px;height:7px;border-radius:50%}.ch.on .dot{display:none}
.bd{padding:14px 16px;display:flex;flex-direction:column;gap:18px}
.hero{border-radius:15px;overflow:hidden;border:0.5px solid var(--bd);background:var(--surf);display:block;transition:transform .25s;position:relative}
.hero:hover{transform:translateY(-3px)}
.herolink{text-decoration:none;color:inherit;display:block}
.favbtn-hero{position:absolute;top:11px;right:11px;z-index:4}
.herowrap{margin:0 -16px;overflow:hidden}
.herotrack{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;padding:0 16px 2px}
.herotrack::-webkit-scrollbar{display:none}
.herotrack .hero{flex:0 0 86%;scroll-snap-align:start;min-width:0}
.heroimg{height:128px;position:relative;overflow:hidden;background:#13243a}
.ha{position:absolute;inset:0;background:radial-gradient(circle at 30% 38%,#1d6fc0 0,transparent 55%),radial-gradient(circle at 76% 66%,#0f3d6e 0,transparent 60%),#13243a}
.hm{position:absolute;inset:0;background:repeating-linear-gradient(60deg,transparent,transparent 22px,rgba(120,185,255,.07) 22px,rgba(120,185,255,.07) 23px),repeating-linear-gradient(-60deg,transparent,transparent 22px,rgba(120,185,255,.07) 22px,rgba(120,185,255,.07) 23px)}
.nd{position:absolute;border-radius:50%;background:rgba(155,205,255,.9);animation:flt 4s ease-in-out infinite}
@keyframes flt{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
.hg{position:absolute;right:18px;bottom:6px;font-size:54px;color:rgba(255,255,255,.12)}
.htag{position:absolute;top:11px;left:11px;font-size:10px;font-weight:600;padding:4px 11px;border-radius:20px;background:rgba(255,255,255,.96);color:#185FA5;z-index:3;display:flex;align-items:center;gap:4px}
.hbody{padding:13px 16px 15px}.hmeta{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.badge{font-size:10px;padding:2px 9px;border-radius:10px;font-weight:600}.bhot{background:#FCEBEB;color:#791F1F}
.tm{font-size:10px;color:var(--txt3);margin-left:auto}
.htitle{font-size:16px;font-weight:600;line-height:1.32;margin-bottom:6px}.hsum{font-size:12px;color:var(--txt2);line-height:1.5}
.area{display:flex;flex-direction:column;gap:10px}
.ahd{display:flex;align-items:center;gap:9px}
.aic{width:26px;height:26px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;flex-shrink:0}
.an{font-size:14px;font-weight:600}.ac{font-size:10px;color:var(--txt3);background:var(--surf1);padding:2px 8px;border-radius:10px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px}
.flip{height:158px;perspective:1100px;cursor:pointer;position:relative}
.fin{position:relative;width:100%;height:100%;transition:transform .55s cubic-bezier(.4,.2,.2,1);transform-style:preserve-3d}
.flip:hover .fin,.flip.fl2 .fin{transform:rotateY(180deg)}
.face{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden;border-radius:13px;overflow:hidden;border:0.5px solid var(--bd);background:var(--surf)}
.fbk{transform:rotateY(180deg);padding:12px 13px;display:flex;flex-direction:column}
.fimg{height:74px;position:relative;overflow:hidden;display:flex;align-items:flex-end}
.fimg.hi{align-items:stretch}.fimg img{width:100%;height:100%;object-fit:cover}
.fmesh{position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent,transparent 16px,rgba(255,255,255,.06) 16px,rgba(255,255,255,.06) 17px)}
.fgl{position:absolute;right:9px;top:6px;font-size:27px;color:rgba(255,255,255,.85)}
.fsrc{position:absolute;top:8px;left:8px;font-size:9px;font-weight:600;padding:2px 8px;border-radius:10px;background:rgba(255,255,255,.95);z-index:2}
.fbody{padding:9px 11px 11px}
.ft{font-size:12px;font-weight:600;line-height:1.32;margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.fm{font-size:10px;color:var(--txt3)}.fhint{position:absolute;bottom:7px;right:9px;font-size:13px;color:var(--txt3);opacity:.5}
.fblbl{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px}
.fbt{font-size:11px;font-weight:600;line-height:1.3;margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.fba{font-size:10px;color:var(--txt2);line-height:1.5;flex:1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical}
.fbtn{margin-top:7px;font-size:10px;color:var(--accent);display:flex;align-items:center;gap:4px;font-weight:600;text-decoration:none}
.searchbar{padding:12px 16px 0}.searchbar input{width:100%;height:38px;border:0.5px solid var(--bd);background:var(--surf);color:var(--txt);border-radius:10px;padding:0 14px;font-size:14px;outline:none}
.searchbar input:focus{border-color:var(--accent)}
.rangebar{padding:9px 16px 0;display:flex;align-items:center;gap:6px}
.rangebar input[type=date]{flex:1;height:34px;border:0.5px solid var(--bd);background:var(--surf);color:var(--txt);border-radius:8px;padding:0 8px;font-size:12px;outline:none;min-width:0;color-scheme:light dark}
.rangebar input[type=date]:focus{border-color:var(--accent)}
.rangeto{font-size:11px;color:var(--txt3);flex-shrink:0}
.rangebar button{border:0.5px solid var(--bd);background:var(--surf);color:var(--txt2);width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0}
.rangebar button:hover{border-color:var(--bds)}
.scope{font-size:11px;color:var(--txt3);padding:6px 16px 0;display:flex;align-items:center;gap:5px}
.timeline{padding:11px 16px;display:flex;gap:6px;overflow-x:auto;border-bottom:0.5px solid var(--bd);scrollbar-width:none}
.timeline::-webkit-scrollbar{display:none}
.mo{font-size:12px;padding:6px 13px;border-radius:20px;border:0.5px solid var(--bd);background:var(--surf);color:var(--txt2);cursor:pointer;white-space:nowrap;display:flex;flex-direction:column;align-items:center;line-height:1.2;user-select:none}
.mo.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}.mo .cnt{font-size:9px;opacity:.7;margin-top:1px}
.daygroup{display:flex;flex-direction:column;gap:10px}
.dlabel{font-size:11px;font-weight:600;color:var(--txt3);letter-spacing:.05em;text-transform:uppercase;display:flex;align-items:center;gap:8px;padding:3px 0}
.dlabel::after{content:'';flex:1;height:0.5px;background:var(--bd)}
.row{display:flex;gap:8px;padding:11px 12px;border:0.5px solid var(--bd);border-radius:12px;background:var(--surf);transition:border-color .2s,transform .18s;align-items:flex-start}
.row:hover{border-color:var(--bds);transform:translateX(2px)}
.rlink{display:flex;gap:11px;flex:1;min-width:0;text-decoration:none;color:inherit;align-items:flex-start}
.favbtn{border:none;background:rgba(0,0,0,.42);color:#fff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:17px;flex-shrink:0;transition:background .15s,transform .12s}
.favbtn:active{transform:scale(.86)}
.favbtn.on{background:#DB3250}
.favbtn-tile{position:absolute;top:6px;right:6px;z-index:4}
.favbtn-row{margin-top:1px}
.ric{width:38px;height:38px;border-radius:9px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:17px;color:#fff;position:relative;overflow:hidden}
.ric::after{content:'';position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent,transparent 5px,rgba(255,255,255,.1) 5px,rgba(255,255,255,.1) 10px)}
.rc{flex:1;min-width:0}.rtop{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.abdg{font-size:9px;padding:1px 7px;border-radius:9px;font-weight:600}
.rtime{font-size:10px;color:var(--txt3);margin-left:auto;white-space:nowrap}
.rt{font-size:13px;font-weight:600;line-height:1.35;margin-bottom:4px}
.rs{font-size:11px;color:var(--txt2);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.loadmore{text-align:center;padding:6px 0 0}
.loadmore button{font-size:12px;color:var(--accent);background:none;border:0.5px solid var(--bd);border-radius:20px;padding:8px 18px;cursor:pointer;font-weight:600}
.empty{text-align:center;padding:50px 20px;color:var(--txt3)}.empty i{font-size:30px;display:block;margin-bottom:10px}
.foot{text-align:center;font-size:11px;color:var(--txt3);padding:24px 16px 0}
</style></head><body>
<div class="shell">
  <div class="hd">
    <div class="hdt">
      <div class="brand"><div class="logo"><i class="ti ti-sparkles"></i></div>
      <div><div class="bn">AI digest</div><div class="bs" id="sub"></div></div></div>
      <span class="live"><span class="ld"></span>Live</span>
    </div>
    <div class="tabs">
      <div class="tab on" id="tabToday" onclick="go('today')"><i class="ti ti-news" style="font-size:14px"></i> Today</div>
      <div class="tab" id="tabWeekly" onclick="go('weekly')"><i class="ti ti-calendar-week" style="font-size:14px"></i> Weekly</div>
      <div class="tab" id="tabArchive" onclick="go('archive')"><i class="ti ti-archive" style="font-size:14px"></i> Archive</div>
      <div class="tab" id="tabFavorites" onclick="go('favorites')"><i class="ti ti-heart" style="font-size:14px"></i> Favorites</div>
    </div>
  </div>
  <div class="view on" id="today"><div class="fl" id="filters"></div><div class="bd" id="todayFeed"></div></div>
  <div class="view" id="weekly"><div class="fl" id="filtersWeek"></div><div class="bd" id="weeklyFeed"></div></div>
  <div class="view" id="archive">
    <div class="searchbar"><input id="q" type="text" placeholder="Search the archive…"></div>
    <div class="fl" id="filtersArchiveTopic"></div>
    <div class="rangebar">
      <input id="rangeFrom" type="date" aria-label="From date">
      <span class="rangeto">to</span>
      <input id="rangeTo" type="date" aria-label="To date">
      <button id="rangeClear" onclick="clearRange()" aria-label="Clear date filter"><i class="ti ti-x" style="font-size:13px"></i></button>
    </div>
    <div class="scope"><i class="ti ti-world-search" style="font-size:12px"></i> <span id="scope">fuzzy search across full archive</span></div>
    <div class="timeline" id="timeline"></div>
    <div class="bd" id="archiveFeed"></div>
  </div>
  <div class="view" id="favorites"><div class="fl" id="filtersFav"></div><div class="bd" id="favFeed"></div></div>
  <div class="foot" id="foot"></div>
</div>
<script>
const D=__DATA__;
const COVER={graphics:"#7a3216",quantum:"#3a3477",hallucination:"#7a2848",cognition:"#0c5742",knowledge_graphs:"#0c447c",systems:"#633806",agents:"#0c5742",multimodal:"#7a3216",models:"#0c447c",training:"#173404",general:"#2c2c2a"};
const KIND={paper:["arXiv"],company:["Lab"],news:["News"],blog:["Digest"],community:["Reddit"],video:["Video"]};
let filterToday="all",filterWeek="all",filterFav="all",archiveTopic="all",activeMonth=null,rangeFrom="",rangeTo="",page=1,query="",curView="today";

// --- Favorites ---------------------------------------------------------
// Stored in this browser's localStorage only. This is a static site with
// no backend, so there's nowhere to persist a "favorite" per-user server
// side — localStorage keeps it per-browser/device, which is the correct
// (and only free) option here. It won't sync across devices.
const FAV_KEY="digest_favs_v1";
function loadFavs(){try{return new Set(JSON.parse(localStorage.getItem(FAV_KEY)||"[]"))}catch(e){return new Set()}}
function saveFavs(){localStorage.setItem(FAV_KEY,JSON.stringify([...favs]))}
let favs=loadFavs();
const itemsById={};D.archive.forEach(it=>itemsById[it.id]=it);
function isFav(id){return favs.has(id)}
function heartBtn(id,extraClass){const on=isFav(id);return `<button class="favbtn ${extraClass||''} ${on?'on':''}" data-fav-id="${esc(id)}" onclick="toggleFav('${id}',event)" aria-label="Favorite"><i class="ti ${on?'ti-heart-filled':'ti-heart'}"></i></button>`}
function toggleFav(id,ev){
  if(ev){ev.preventDefault();ev.stopPropagation()}
  if(favs.has(id))favs.delete(id);else favs.add(id);
  saveFavs();
  syncHearts(id);
  if(curView==="favorites")renderFavorites();
}
function syncHearts(id){
  document.querySelectorAll("[data-fav-id]").forEach(el=>{
    if(el.getAttribute("data-fav-id")!==id)return;
    const on=isFav(id);
    el.classList.toggle("on",on);
    const ic=el.querySelector("i");
    if(ic)ic.className="ti "+(on?"ti-heart-filled":"ti-heart");
  });
}

function esc(s){const d=document.createElement("div");d.textContent=s||"";return d.innerHTML}
function ago(iso){if(!iso)return"";const s=(Date.now()-new Date(iso).getTime())/1000;if(s<3600)return Math.floor(s/60)+"m ago";if(s<86400)return Math.floor(s/3600)+"h ago";return Math.floor(s/86400)+"d ago"}
function cover(it){const c=COVER[it.area]||"#2c2c2a";if(it.image)return `<div class="fimg hi"><img src="${esc(it.image)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.classList.remove('hi');this.remove()"><span class="fsrc" style="color:${c}">${esc((KIND[it.source_kind]||[''])[0])}</span></div>`;return `<div class="fimg" style="background:${c}"><div class="fmesh"></div><span class="fsrc" style="color:${c}">${esc((KIND[it.source_kind]||[''])[0])}</span><span class="fgl"><i class="ti ${esc(it.area_glyph)}"></i></span></div>`}
function card(it){return `<div class="flip" onclick="this.classList.toggle('fl2')"><div class="fin"><div class="face">${cover(it)}<div class="fbody"><div class="ft">${esc(it.title)}</div><div class="fm">${esc(it.source)} · ${ago(it.published)}</div></div><span class="fhint"><i class="ti ti-rotate-2"></i></span></div><div class="face fbk"><div class="fblbl" style="color:${it.area_color}">${esc(it.area_label)}</div><div class="fbt">${esc(it.title)}</div><div class="fba">${esc(it.summary)||"No summary."}</div><a class="fbtn" href="${esc(it.link)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Read <i class="ti ti-external-link" style="font-size:10px"></i></a></div></div>${heartBtn(it.id,'favbtn-tile')}</div>`}
function heroHTML(it){if(!it)return"";const nodes=[[22,35,8,0],[48,55,6,.6],[68,30,10,1.1],[80,62,5,1.7],[35,70,7,.9]].map(n=>`<div class="nd" style="left:${n[0]}%;top:${n[1]}%;width:${n[2]}px;height:${n[2]}px;animation-delay:${n[3]}s"></div>`).join("");return `<div class="hero">${heartBtn(it.id,'favbtn-hero')}<a class="herolink" href="${esc(it.link)}" target="_blank" rel="noopener"><div class="heroimg"><div class="ha"></div><div class="hm"></div>${nodes}<span class="htag"><i class="ti ti-flame" style="font-size:10px"></i> Top story</span><span class="hg"><i class="ti ${esc(it.area_glyph)}"></i></span></div><div class="hbody"><div class="hmeta"><span class="badge" style="background:#E6F1FB;color:#0C447C">${esc(it.area_label)}</span>${it.is_hot?'<span class="badge bhot">Hot</span>':''}<span class="tm">${ago(it.published)}</span></div><div class="htitle">${esc(it.title)}</div><div class="hsum">${esc(it.summary)}</div></div></a></div>`}
function heroCarousel(items){
  if(!items||!items.length)return"";
  if(items.length===1)return heroHTML(items[0]);
  return `<div class="herowrap"><div class="herotrack">${items.map(heroHTML).join("")}</div></div>`;
}
function renderToday(){
  const fl=document.getElementById("filters");
  let c=`<div class="ch ${filterToday==='all'?'on':''}" onclick="setFilter('today','all')">All areas</div>`;
  for(const[id,a] of Object.entries(D.areas))c+=`<div class="ch ${filterToday===id?'on':''}" onclick="setFilter('today','${id}')"><span class="dot" style="background:${a.color}"></span>${esc(a.label.split(' ')[0])}</div>`;
  fl.innerHTML=c;
  let out="";
  if(filterToday==="all"&&D.heroes&&D.heroes.length)out+=heroCarousel(D.heroes);
  for(const[id,a] of Object.entries(D.areas)){
    if(filterToday!=="all"&&filterToday!==id)continue;
    out+=`<div class="area"><div class="ahd"><div class="aic" style="background:${a.color}"><i class="ti ${esc(a.glyph)}"></i></div><span class="an">${esc(a.label)}</span><span class="ac">${a.items.length}</span></div><div class="tiles">${a.items.map(card).join("")}</div></div>`;
  }
  if(!out)out=`<div class="empty"><i class="ti ti-coffee"></i>Nothing new in the current window.</div>`;
  document.getElementById("todayFeed").innerHTML=out;
}
function renderWeekly(){
  const fl=document.getElementById("filtersWeek");
  let c=`<div class="ch ${filterWeek==='all'?'on':''}" onclick="setFilter('weekly','all')">All areas</div>`;
  for(const[id,a] of Object.entries(D.areas_weekly))c+=`<div class="ch ${filterWeek===id?'on':''}" onclick="setFilter('weekly','${id}')"><span class="dot" style="background:${a.color}"></span>${esc(a.label.split(' ')[0])}</div>`;
  fl.innerHTML=c;
  let out="";
  if(filterWeek==="all"&&D.heroes_week&&D.heroes_week.length)out+=heroCarousel(D.heroes_week);
  for(const[id,a] of Object.entries(D.areas_weekly)){
    if(filterWeek!=="all"&&filterWeek!==id)continue;
    out+=`<div class="area"><div class="ahd"><div class="aic" style="background:${a.color}"><i class="ti ${esc(a.glyph)}"></i></div><span class="an">${esc(a.label)}</span><span class="ac">${a.items.length}</span></div><div class="tiles">${a.items.map(card).join("")}</div></div>`;
  }
  if(!out)out=`<div class="empty"><i class="ti ti-calendar-week"></i>Nothing from the past week yet.</div>`;
  document.getElementById("weeklyFeed").innerHTML=out;
}
function renderFavorites(){
  const fl=document.getElementById("filtersFav");
  const favItems=[...favs].map(id=>itemsById[id]).filter(Boolean);
  const groups={};
  for(const it of favItems){
    if(!groups[it.area])groups[it.area]={label:it.area_label,color:it.area_color,glyph:it.area_glyph,items:[]};
    groups[it.area].items.push(it);
  }
  for(const g of Object.values(groups))g.items.sort((a,b)=>(b.published_ts||0)-(a.published_ts||0));
  const ordered=D.area_order.filter(a=>groups[a.id]).map(a=>[a.id,groups[a.id]]);
  let c=`<div class="ch ${filterFav==='all'?'on':''}" onclick="setFilter('favorites','all')">All areas</div>`;
  for(const[id,g] of ordered)c+=`<div class="ch ${filterFav===id?'on':''}" onclick="setFilter('favorites','${id}')"><span class="dot" style="background:${g.color}"></span>${esc(g.label.split(' ')[0])}</div>`;
  fl.innerHTML=c;
  let out="";
  for(const[id,g] of ordered){
    if(filterFav!=="all"&&filterFav!==id)continue;
    out+=`<div class="area"><div class="ahd"><div class="aic" style="background:${g.color}"><i class="ti ${esc(g.glyph)}"></i></div><span class="an">${esc(g.label)}</span><span class="ac">${g.items.length}</span></div><div class="tiles">${g.items.map(card).join("")}</div></div>`;
  }
  if(!favItems.length)out=`<div class="empty"><i class="ti ti-heart"></i>No favorites yet — tap the heart on any story to save it here.</div>`;
  document.getElementById("favFeed").innerHTML=out;
}
let mini=null;
function buildIndex(){
  mini=new MiniSearch({fields:["title","summary","area_label","source"],storeFields:["id","title","summary","link","source","source_kind","published","published_ts","area","area_label","area_color","area_glyph"],searchOptions:{boost:{title:2},fuzzy:.2,prefix:true}});
  mini.addAll(D.archive.map((it,i)=>({_idx:i,...it})));
}
function archRow(it){return `<div class="row"><a class="rlink" href="${esc(it.link)}" target="_blank" rel="noopener"><div class="ric" style="background:${it.area_color}"><i class="ti ${esc(it.area_glyph)}" style="position:relative;z-index:1"></i></div><div class="rc"><div class="rtop"><span class="abdg" style="background:${it.area_color}22;color:${it.area_color}">${esc(it.area_label.split(' ')[0])}</span><span class="rtime">${ago(it.published)}</span></div><div class="rt">${esc(it.title)}</div><div class="rs">${esc(it.summary)}</div></div></a>${heartBtn(it.id,'favbtn-row')}</div>`}
function archiveTopicChips(){
  const counts={};
  for(const it of D.archive)counts[it.area]=(counts[it.area]||0)+1;
  const present=D.area_order.filter(a=>counts[a.id]);
  let c=`<div class="ch ${archiveTopic==='all'?'on':''}" onclick="setArchiveTopic('all')">All topics</div>`;
  for(const a of present)c+=`<div class="ch ${archiveTopic===a.id?'on':''}" onclick="setArchiveTopic('${a.id}')"><span class="dot" style="background:${a.color}"></span>${esc(a.label.split(' ')[0])} <span style="opacity:.65">${counts[a.id]}</span></div>`;
  document.getElementById("filtersArchiveTopic").innerHTML=c;
}
function setArchiveTopic(id){archiveTopic=id;page=1;renderArchive()}
function clearRange(){
  rangeFrom="";rangeTo="";
  document.getElementById("rangeFrom").value="";
  document.getElementById("rangeTo").value="";
  page=1;renderArchive();
}
function renderArchive(){
  archiveTopicChips();
  const tl=document.getElementById("timeline");
  let t="";
  for(const[ym,n] of D.months){const lbl=new Date(ym+"-01").toLocaleDateString(undefined,{month:"short",year:"2-digit"});t+=`<div class="mo ${activeMonth===ym?'on':''}" onclick="setMonth('${ym}')">${lbl}<span class="cnt">${n}</span></div>`}
  tl.innerHTML=t;

  let items,scopeBase,isQuery=false;
  if(query){
    items=mini.search(query).map(r=>r);
    scopeBase=`results for "${query}"`;
    isQuery=true;
  }else{
    items=D.archive.filter(it=>{
      const day=(it.published||"").slice(0,10);
      const ym=(it.published||"").slice(0,7);
      if(rangeFrom||rangeTo){
        if(rangeFrom&&(!day||day<rangeFrom))return false;
        if(rangeTo&&(!day||day>rangeTo))return false;
        return true;
      }
      return !activeMonth||ym===activeMonth;
    });
    if(rangeFrom||rangeTo){
      scopeBase=rangeFrom&&rangeTo
        ?(rangeFrom===rangeTo?`on ${rangeFrom}`:`from ${rangeFrom} to ${rangeTo}`)
        :rangeFrom?`from ${rangeFrom} onward`:`up to ${rangeTo}`;
    }else if(activeMonth){
      scopeBase=`in ${activeMonth}`;
    }else{
      scopeBase=`across the full archive`;
    }
  }
  if(archiveTopic!=="all"){
    items=items.filter(it=>it.area===archiveTopic);
    const a=D.area_order.find(x=>x.id===archiveTopic);
    if(a)scopeBase+=` · ${a.label}`;
  }
  document.getElementById("scope").textContent=isQuery?`${items.length} ${scopeBase}`:`${items.length} items ${scopeBase}`;

  const shown=items.slice(0,page*40);
  // group by day
  let out="",lastDay="";
  for(const it of shown){const day=(it.published||"").slice(0,10);if(day!==lastDay){if(lastDay)out+="</div>";const lbl=day?new Date(day).toLocaleDateString(undefined,{month:"short",day:"numeric"}):"Undated";out+=`<div class="daygroup"><div class="dlabel">${lbl}</div>`;lastDay=day}out+=archRow(it)}
  if(lastDay)out+="</div>";
  if(!shown.length)out=`<div class="empty"><i class="ti ti-search-off"></i>No items match.</div>`;
  if(shown.length<items.length)out+=`<div class="loadmore"><button onclick="page++;renderArchive()">Load more (${items.length-shown.length} more) <i class="ti ti-chevron-down" style="font-size:11px"></i></button></div>`;
  document.getElementById("archiveFeed").innerHTML=out;
}
function setFilter(view,id){
  if(view==="today"){filterToday=id;renderToday()}
  else if(view==="weekly"){filterWeek=id;renderWeekly()}
  else if(view==="favorites"){filterFav=id;renderFavorites()}
}
function setMonth(ym){
  activeMonth=activeMonth===ym?null:ym;
  page=1;query="";document.getElementById("q").value="";
  rangeFrom="";rangeTo="";
  document.getElementById("rangeFrom").value="";
  document.getElementById("rangeTo").value="";
  renderArchive();
}
function go(which){
  curView=which;
  for(const w of["Today","Weekly","Archive","Favorites"])document.getElementById("tab"+w).classList.toggle("on",which===w.toLowerCase());
  for(const w of["today","weekly","archive","favorites"])document.getElementById(w).classList.toggle("on",which===w);
  if(which==="today")document.getElementById("sub").textContent=`Updated ${ago(D.generated_at)} · ${D.today_count} today`;
  else if(which==="weekly")document.getElementById("sub").textContent=`Updated ${ago(D.generated_at)} · ${D.weekly_count} this week`;
  else if(which==="archive")document.getElementById("sub").textContent=`${D.archive_total} archived · since ${D.oldest||"—"}`;
  else if(which==="favorites")document.getElementById("sub").textContent=`${favs.size} saved`;
  if(which==="archive"){if(!mini)buildIndex();renderArchive()}
  if(which==="weekly")renderWeekly();
  if(which==="favorites")renderFavorites();
}
document.getElementById("q").addEventListener("input",e=>{query=e.target.value.trim();page=1;if(query)activeMonth=null;renderArchive()});
document.getElementById("rangeFrom").addEventListener("change",e=>{rangeFrom=e.target.value;if(rangeFrom||rangeTo)activeMonth=null;page=1;renderArchive()});
document.getElementById("rangeTo").addEventListener("change",e=>{rangeTo=e.target.value;if(rangeFrom||rangeTo)activeMonth=null;page=1;renderArchive()});
renderToday();
document.getElementById("sub").textContent=`Updated ${ago(D.generated_at)} · ${D.today_count} today`;
document.getElementById("foot").textContent=`Generated ${new Date(D.generated_at).toLocaleString()} · ${D.archive_total} items archived · refreshes daily`;
</script></body></html>"""

if __name__ == "__main__":
    build()
