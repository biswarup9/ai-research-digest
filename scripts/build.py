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

import sources as cfg
import db

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "site" / "index.html"


def build():
    conn = db.connect()
    recent = db.recent_items(conn, cfg.TODAY_WINDOW_DAYS)
    archive = db.all_items(conn)
    months = db.month_counts(conn)
    st = db.stats(conn)
    conn.close()

    # Today: group recent items by area (config order), pick hero
    by_area = {}
    for area in cfg.TOPIC_AREAS:
        members = [i for i in recent if i["area"] == area["id"]]
        if members:
            by_area[area["id"]] = {
                "label": area["label"], "color": area["color"],
                "glyph": area["glyph"], "items": members,
            }
    hero = next((i for i in recent if i["is_hot"]), recent[0] if recent else None)

    oldest = None
    if st["oldest_ts"]:
        oldest = datetime.fromtimestamp(st["oldest_ts"], timezone.utc).strftime("%b %Y")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today_count": len(recent),
        "archive_total": st["total"],
        "oldest": oldest,
        "hero": hero,
        "areas": by_area,
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
.tab{flex:1;text-align:center;font-size:13px;font-weight:600;padding:11px 0;color:var(--txt3);cursor:pointer;border-bottom:2px solid transparent;display:flex;align-items:center;justify-content:center;gap:6px;user-select:none}
.tab.on{color:var(--txt);border-bottom-color:var(--accent)}
.view{display:none}.view.on{display:block}
.fl{padding:11px 16px;display:flex;gap:6px;overflow-x:auto;border-bottom:0.5px solid var(--bd);scrollbar-width:none}
.fl::-webkit-scrollbar{display:none}
.ch{font-size:12px;padding:6px 12px;border-radius:20px;border:0.5px solid var(--bd);background:var(--surf);color:var(--txt2);cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:5px;user-select:none}
.ch.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}.ch .dot{width:7px;height:7px;border-radius:50%}.ch.on .dot{display:none}
.bd{padding:14px 16px;display:flex;flex-direction:column;gap:18px}
.hero{border-radius:15px;overflow:hidden;border:0.5px solid var(--bd);background:var(--surf);text-decoration:none;color:inherit;display:block;transition:transform .25s}
.hero:hover{transform:translateY(-3px)}
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
.flip{height:158px;perspective:1100px;cursor:pointer}
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
.scope{font-size:11px;color:var(--txt3);padding:6px 16px 0;display:flex;align-items:center;gap:5px}
.timeline{padding:11px 16px;display:flex;gap:6px;overflow-x:auto;border-bottom:0.5px solid var(--bd);scrollbar-width:none}
.timeline::-webkit-scrollbar{display:none}
.mo{font-size:12px;padding:6px 13px;border-radius:20px;border:0.5px solid var(--bd);background:var(--surf);color:var(--txt2);cursor:pointer;white-space:nowrap;display:flex;flex-direction:column;align-items:center;line-height:1.2;user-select:none}
.mo.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}.mo .cnt{font-size:9px;opacity:.7;margin-top:1px}
.daygroup{display:flex;flex-direction:column;gap:10px}
.dlabel{font-size:11px;font-weight:600;color:var(--txt3);letter-spacing:.05em;text-transform:uppercase;display:flex;align-items:center;gap:8px;padding:3px 0}
.dlabel::after{content:'';flex:1;height:0.5px;background:var(--bd)}
.row{display:flex;gap:11px;padding:11px 12px;border:0.5px solid var(--bd);border-radius:12px;background:var(--surf);text-decoration:none;color:inherit;transition:border-color .2s,transform .18s;align-items:flex-start}
.row:hover{border-color:var(--bds);transform:translateX(2px)}
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
      <div class="tab" id="tabArchive" onclick="go('archive')"><i class="ti ti-archive" style="font-size:14px"></i> Archive</div>
    </div>
  </div>
  <div class="view on" id="today"><div class="fl" id="filters"></div><div class="bd" id="todayFeed"></div></div>
  <div class="view" id="archive">
    <div class="searchbar"><input id="q" type="text" placeholder="Search the archive…"></div>
    <div class="scope"><i class="ti ti-world-search" style="font-size:12px"></i> <span id="scope">fuzzy search across full archive</span></div>
    <div class="timeline" id="timeline"></div>
    <div class="bd" id="archiveFeed"></div>
  </div>
  <div class="foot" id="foot"></div>
</div>
<script>
const D=__DATA__;
const COVER={graphics:"#7a3216",quantum:"#3a3477",hallucination:"#7a2848",cognition:"#0c5742",knowledge_graphs:"#0c447c",systems:"#633806",agents:"#0c5742",multimodal:"#7a3216",models:"#0c447c",training:"#173404",general:"#2c2c2a"};
const KIND={paper:["arXiv"],company:["Lab"],news:["News"],blog:["Digest"],community:["Reddit"],video:["Video"]};
let filter="all",activeMonth=null,page=1,query="";
function esc(s){const d=document.createElement("div");d.textContent=s||"";return d.innerHTML}
function ago(iso){if(!iso)return"";const s=(Date.now()-new Date(iso).getTime())/1000;if(s<3600)return Math.floor(s/60)+"m ago";if(s<86400)return Math.floor(s/3600)+"h ago";return Math.floor(s/86400)+"d ago"}
function cover(it){const c=COVER[it.area]||"#2c2c2a";if(it.image)return `<div class="fimg hi"><img src="${esc(it.image)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.classList.remove('hi');this.remove()"><span class="fsrc" style="color:${c}">${esc((KIND[it.source_kind]||[''])[0])}</span></div>`;return `<div class="fimg" style="background:${c}"><div class="fmesh"></div><span class="fsrc" style="color:${c}">${esc((KIND[it.source_kind]||[''])[0])}</span><span class="fgl"><i class="ti ${esc(it.area_glyph)}"></i></span></div>`}
function card(it){return `<div class="flip" onclick="this.classList.toggle('fl2')"><div class="fin"><div class="face">${cover(it)}<div class="fbody"><div class="ft">${esc(it.title)}</div><div class="fm">${esc(it.source)} · ${ago(it.published)}</div></div><span class="fhint"><i class="ti ti-rotate-2"></i></span></div><div class="face fbk"><div class="fblbl" style="color:${it.area_color}">${esc(it.area_label)}</div><div class="fbt">${esc(it.title)}</div><div class="fba">${esc(it.summary)||"No summary."}</div><a class="fbtn" href="${esc(it.link)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Read <i class="ti ti-external-link" style="font-size:10px"></i></a></div></div></div>`}
function heroHTML(it){if(!it)return"";const nodes=[[22,35,8,0],[48,55,6,.6],[68,30,10,1.1],[80,62,5,1.7],[35,70,7,.9]].map(n=>`<div class="nd" style="left:${n[0]}%;top:${n[1]}%;width:${n[2]}px;height:${n[2]}px;animation-delay:${n[3]}s"></div>`).join("");return `<a class="hero" href="${esc(it.link)}" target="_blank" rel="noopener"><div class="heroimg"><div class="ha"></div><div class="hm"></div>${nodes}<span class="htag"><i class="ti ti-flame" style="font-size:10px"></i> Top story</span><span class="hg"><i class="ti ${esc(it.area_glyph)}"></i></span></div><div class="hbody"><div class="hmeta"><span class="badge" style="background:#E6F1FB;color:#0C447C">${esc(it.area_label)}</span>${it.is_hot?'<span class="badge bhot">Hot</span>':''}<span class="tm">${ago(it.published)}</span></div><div class="htitle">${esc(it.title)}</div><div class="hsum">${esc(it.summary)}</div></div></a>`}
function renderToday(){
  const fl=document.getElementById("filters");
  let c=`<div class="ch ${filter==='all'?'on':''}" onclick="setF('all')">All areas</div>`;
  for(const[id,a] of Object.entries(D.areas))c+=`<div class="ch ${filter===id?'on':''}" onclick="setF('${id}')"><span class="dot" style="background:${a.color}"></span>${esc(a.label.split(' ')[0])}</div>`;
  fl.innerHTML=c;
  let out="";
  if(filter==="all"&&D.hero)out+=heroHTML(D.hero);
  for(const[id,a] of Object.entries(D.areas)){
    if(filter!=="all"&&filter!==id)continue;
    out+=`<div class="area"><div class="ahd"><div class="aic" style="background:${a.color}"><i class="ti ${esc(a.glyph)}"></i></div><span class="an">${esc(a.label)}</span><span class="ac">${a.items.length}</span></div><div class="tiles">${a.items.map(card).join("")}</div></div>`;
  }
  if(!out)out=`<div class="empty"><i class="ti ti-coffee"></i>Nothing new in the current window.</div>`;
  document.getElementById("todayFeed").innerHTML=out;
}
let mini=null;
function buildIndex(){
  mini=new MiniSearch({fields:["title","summary","area_label","source"],storeFields:["title","summary","link","source","source_kind","published","area","area_label","area_color","area_glyph"],searchOptions:{boost:{title:2},fuzzy:.2,prefix:true}});
  mini.addAll(D.archive.map((it,i)=>({id:i,...it})));
}
function archRow(it){const k=(KIND[it.source_kind]||[''])[0];return `<a class="row" href="${esc(it.link)}" target="_blank" rel="noopener"><div class="ric" style="background:${it.area_color}"><i class="ti ${esc(it.area_glyph)}" style="position:relative;z-index:1"></i></div><div class="rc"><div class="rtop"><span class="abdg" style="background:${it.area_color}22;color:${it.area_color}">${esc(it.area_label.split(' ')[0])}</span><span class="rtime">${ago(it.published)}</span></div><div class="rt">${esc(it.title)}</div><div class="rs">${esc(it.summary)}</div></div></a>`}
function renderArchive(){
  const tl=document.getElementById("timeline");
  let t="";
  for(const[ym,n] of D.months){const lbl=new Date(ym+"-01").toLocaleDateString(undefined,{month:"short",year:"2-digit"});t+=`<div class="mo ${activeMonth===ym?'on':''}" onclick="setMonth('${ym}')">${lbl}<span class="cnt">${n}</span></div>`}
  tl.innerHTML=t;
  let items;
  if(query){items=mini.search(query).map(r=>r);document.getElementById("scope").textContent=`${items.length} results for "${query}"`}
  else{items=D.archive.filter(it=>!activeMonth||(it.published||"").slice(0,7)===activeMonth);document.getElementById("scope").textContent=activeMonth?`${items.length} items in ${activeMonth}`:`fuzzy search across ${D.archive_total} items`}
  const shown=items.slice(0,page*40);
  // group by day
  let out="",lastDay="";
  for(const it of shown){const day=(it.published||"").slice(0,10);if(day!==lastDay){if(lastDay)out+="</div>";const lbl=day?new Date(day).toLocaleDateString(undefined,{month:"short",day:"numeric"}):"Undated";out+=`<div class="daygroup"><div class="dlabel">${lbl}</div>`;lastDay=day}out+=archRow(it)}
  if(lastDay)out+="</div>";
  if(!shown.length)out=`<div class="empty"><i class="ti ti-search-off"></i>No items match.</div>`;
  if(shown.length<items.length)out+=`<div class="loadmore"><button onclick="page++;renderArchive()">Load more (${items.length-shown.length} more) <i class="ti ti-chevron-down" style="font-size:11px"></i></button></div>`;
  document.getElementById("archiveFeed").innerHTML=out;
}
function setF(id){filter=id;renderToday()}
function setMonth(ym){activeMonth=activeMonth===ym?null:ym;page=1;query="";document.getElementById("q").value="";renderArchive()}
function go(which){
  document.getElementById("tabToday").classList.toggle("on",which==="today");
  document.getElementById("tabArchive").classList.toggle("on",which==="archive");
  document.getElementById("today").classList.toggle("on",which==="today");
  document.getElementById("archive").classList.toggle("on",which==="archive");
  document.getElementById("sub").textContent=which==="today"?`Updated ${ago(D.generated_at)} · ${D.today_count} today`:`${D.archive_total} archived · since ${D.oldest||"—"}`;
  if(which==="archive"&&!mini)buildIndex();
}
document.getElementById("q").addEventListener("input",e=>{query=e.target.value.trim();page=1;if(query)activeMonth=null;renderArchive()});
renderToday();
document.getElementById("sub").textContent=`Updated ${ago(D.generated_at)} · ${D.today_count} today`;
document.getElementById("foot").textContent=`Generated ${new Date(D.generated_at).toLocaleString()} · ${D.archive_total} items archived · refreshes daily`;
</script></body></html>"""

if __name__ == "__main__":
    build()
