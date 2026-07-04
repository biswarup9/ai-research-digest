"""
summarize.py — free extractive summarization. No LLM, no API key.

Strategy: most feeds already give a usable abstract/summary. We turn that
into a clean 1-2 sentence "why it matters" blurb by:
  1. splitting into sentences,
  2. scoring each by keyword density + position (lead bias),
  3. keeping the top 2 in original order.

This is deterministic, instant, and runs free inside GitHub Actions.
If a summary is already short, we return it as-is.
"""

import re
from collections import Counter

STOP = set("""a an the of to in on for and or but with from by as is are was were be
been being this that these those it its their his her our your my we you they he she
i at into over under about above below after before than then so such can will may might
""".split())


def split_sentences(text):
    # naive but robust sentence splitter
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 0]


def summarize(text, max_sentences=2, max_chars=260):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    sents = split_sentences(text)
    if len(sents) <= max_sentences:
        out = " ".join(sents)
        return out[:max_chars].rsplit(" ", 1)[0] + "…" if len(out) > max_chars else out

    # word frequency table (excluding stopwords) for scoring
    words = re.findall(r"[a-z']+", text.lower())
    freq = Counter(w for w in words if w not in STOP and len(w) > 2)
    if not freq:
        freq = Counter(words)
    top = max(freq.values())

    scored = []
    for idx, s in enumerate(sents):
        sw = re.findall(r"[a-z']+", s.lower())
        if not sw:
            continue
        density = sum(freq.get(w, 0) for w in sw) / (len(sw) * top)
        position_bonus = 0.25 if idx == 0 else 0.1 if idx == 1 else 0
        scored.append((density + position_bonus, idx, s))

    scored.sort(reverse=True)
    chosen = sorted(scored[:max_sentences], key=lambda x: x[1])  # original order
    out = " ".join(s for _, _, s in chosen)
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0] + "…"
    return out


if __name__ == "__main__":
    demo = ("We present NEMESIS, a neural rendering system that reconstructs "
            "dynamic 3D scenes at 60fps from sparse multi-view camera input. "
            "Our method outperforms gaussian splatting baselines on temporal "
            "coherence while reducing memory footprint by 40 percent. "
            "We demonstrate results on driving and indoor capture scenes.")
    print(summarize(demo))
