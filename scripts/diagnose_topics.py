"""
diagnose_topics.py — one-off diagnostic. Run from your repo's scripts/ folder:

    python3 diagnose_topics.py

Prints the actual nearest-neighbor cosine-similarity distribution across your
"general" pool, plus how many items would qualify for a cluster under a range
of threshold/min-cluster-size combinations. Use this to pick real numbers for
DYNAMIC_TOPIC_THRESHOLD / DYNAMIC_TOPIC_MIN_CLUSTER in sources.py instead of
guessing — MiniLM similarity on short news/paper titles tends to sit in a
narrower, lower band than people expect, so the default 0.62 may simply be
too strict for your feed's actual text.
"""
import sys
import numpy as np

sys.path.insert(0, ".")
import topics
import db

conn = db.connect()
rows = conn.execute(
    "SELECT id, title, embedding FROM items WHERE area='general' AND embedding IS NOT NULL"
).fetchall()
conn.close()

if len(rows) < 10:
    print(f"Only {len(rows)} embedded 'general' items — not enough to diagnose. "
          f"Run fetch.py again first (it backfills embeddings automatically).")
    sys.exit(0)

embs = np.array([topics.decode_embedding(r["embedding"]) for r in rows], dtype=np.float32)
print(f"General pool size: {len(embs)} items\n")

sims = embs @ embs.T
np.fill_diagonal(sims, -1)  # ignore self-similarity

best = sims.max(axis=1)
print("Nearest-neighbor cosine similarity across the pool (percentiles):")
for p in [50, 75, 90, 95, 99]:
    print(f"  p{p:>2}: {np.percentile(best, p):.3f}")

print("\nA cluster needs min_cluster_size items that are ALL mutually above the "
      "threshold — not just pairs — so this is an upper bound, not a guarantee.\n")

print(f"{'threshold':>10} | items with >=5 neighbors above it (naive upper bound for min_cluster=5)")
for t in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.62, 0.65, 0.70]:
    counts = (sims >= t).sum(axis=1)
    eligible = int((counts >= 4).sum())
    print(f"{t:>10.2f} | {eligible}")

print("\nCurrent config: DYNAMIC_TOPIC_THRESHOLD =", __import__("sources").DYNAMIC_TOPIC_THRESHOLD,
      " DYNAMIC_TOPIC_MIN_CLUSTER =", __import__("sources").DYNAMIC_TOPIC_MIN_CLUSTER)
print("\nPick a threshold from the table above where the 'eligible' count is "
      "comfortably above your min_cluster_size, then update sources.py.")
