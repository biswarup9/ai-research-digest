"""
Central configuration for AI Digest.
Edit THIS file to tune what your feed pulls and how it gets bucketed.
Nothing else needs changing for day-to-day tuning.
"""

# ---------------------------------------------------------------------------
# 1. arXiv categories
# ---------------------------------------------------------------------------
# arXiv exposes a per-category Atom feed at:
#   http://export.arxiv.org/api/query?search_query=cat:<CATEGORY>...
# These categories collectively cover everything you listed: cognition,
# quantum, hallucination, latency, networking/UDP, knowledge graphs, graphics.
ARXIV_CATEGORIES = [
    "cs.AI",    # artificial intelligence (broad, catches hallucination, reasoning)
    "cs.LG",    # machine learning (models, training)
    "cs.CL",    # computation and language (LLMs, NLP)
    "cs.CV",    # computer vision (multimodal, graphics-adjacent)
    "cs.GR",    # graphics (NVIDIA rendering, NeRF, gaussian splatting)
    "cs.NE",    # neural and evolutionary computing (cognition-adjacent)
    "cs.DC",    # distributed/parallel computing (latency, systems, serving)
    "cs.NI",    # networking (UDP, transport, protocols)
    "cs.DB",    # databases (knowledge graphs, retrieval)
    "quant-ph", # quantum physics (quantum computing for/with AI)
]

# How many results to request per category per run.
ARXIV_MAX_PER_CATEGORY = 40

# ---------------------------------------------------------------------------
# 2. RSS / Atom feeds  (company research + news + newsletters)
# ---------------------------------------------------------------------------
# label, url, kind  ->  kind is used for the badge + source icon color.
# kinds: "company", "news", "blog"
RSS_FEEDS = [
    # --- Big-lab / company research blogs ---
    ("Google DeepMind",  "https://deepmind.google/blog/rss.xml",                 "company"),
    ("Google AI",        "https://blog.google/technology/ai/rss/",               "company"),
    ("OpenAI",           "https://openai.com/news/rss.xml",                      "company"),
    ("Microsoft Research","https://www.microsoft.com/en-us/research/feed/",      "company"),
    ("Meta AI",          "https://ai.meta.com/blog/rss/",                        "company"),
    ("NVIDIA Developer", "https://developer.nvidia.com/blog/feed",               "company"),
    ("AWS ML Blog",      "https://aws.amazon.com/blogs/machine-learning/feed/",  "company"),

    # --- News outlets ---
    ("VentureBeat AI",   "https://venturebeat.com/category/ai/feed/",            "news"),
    ("TechCrunch AI",    "https://techcrunch.com/category/artificial-intelligence/feed/", "news"),
    ("MIT Tech Review",  "https://www.technologyreview.com/feed/",               "news"),
    ("Ars Technica",     "https://feeds.arstechnica.com/arstechnica/technology-lab", "news"),

    # --- Newsletters / curated ---
    ("The Batch",        "https://www.deeplearning.ai/the-batch/feed/",          "blog"),
    ("MarkTechPost",     "https://www.marktechpost.com/feed/",                   "blog"),
]

# ---------------------------------------------------------------------------
# 3. Topic areas  (segregation buckets)
# ---------------------------------------------------------------------------
# Each item is assigned to the FIRST area whose keywords match its title or
# summary (case-insensitive, word-ish match). Order matters: most specific
# first. Anything unmatched lands in "General AI".
#
# Add/remove keywords freely. "label" is what shows as the section header,
# "color" is the accent hex used in the UI, "glyph" is a Tabler icon name.
TOPIC_AREAS = [
    {
        "id": "graphics",
        "label": "Graphics & rendering",
        "color": "#D85A30",
        "glyph": "ti-cube",
        "keywords": ["nvidia", "rendering", "render", "graphics", "nerf",
                     "gaussian splat", "ray tracing", "rasteriz", "shader",
                     "neural radiance", "3d reconstruction", "nemesis", "vlss",
                     "dlss", "texture synthesis", "novel view"],
    },
    {
        "id": "quantum",
        "label": "Quantum",
        "color": "#7F77DD",
        "glyph": "ti-atom",
        "keywords": ["quantum", "qubit", "qaoa", "variational quantum",
                     "quantum machine learning", "quantum circuit"],
    },
    {
        "id": "hallucination",
        "label": "Hallucination & reliability",
        "color": "#D4537E",
        "glyph": "ti-alert-triangle",
        "keywords": ["hallucinat", "factual", "faithfulness", "truthful",
                     "calibration", "uncertainty", "reliability", "grounding"],
    },
    {
        "id": "cognition",
        "label": "Cognition & reasoning",
        "color": "#1D9E75",
        "glyph": "ti-brain",
        "keywords": ["cognit", "reasoning", "chain-of-thought", "chain of thought",
                     "planning", "world model", "metacognit", "theory of mind",
                     "self-reflect", "deliberat"],
    },
    {
        "id": "knowledge_graphs",
        "label": "Knowledge graphs & retrieval",
        "color": "#185FA5",
        "glyph": "ti-share",
        "keywords": ["knowledge graph", "knowledge base", "retrieval-augmented",
                     "rag ", "graph neural", "entity linking", "ontolog",
                     "neptune", "cypher", "triple store", "semantic"],
    },
    {
        "id": "systems",
        "label": "Latency, serving & systems",
        "color": "#854F0B",
        "glyph": "ti-bolt",
        "keywords": ["latency", "throughput", "inference serv", "kv cache",
                     "kv-cache", "speculative decod", "quantiz", "distillation",
                     "flashattention", "flash attention", "kernel", "serving",
                     "batching", "udp", "rdma", "transport protocol", "networking"],
    },
    {
        "id": "agents",
        "label": "Agents & tool use",
        "color": "#0F6E56",
        "glyph": "ti-robot",
        "keywords": ["agent", "tool use", "tool-use", "function calling",
                     "mcp", "model context protocol", "trajectory", "autonomous",
                     "multi-agent", "orchestrat"],
    },
    {
        "id": "multimodal",
        "label": "Multimodal & vision",
        "color": "#993C1D",
        "glyph": "ti-eye",
        "keywords": ["multimodal", "vision-language", "vision language", "vlm",
                     "image generation", "video generation", "diffusion",
                     "text-to-image", "text-to-video", "audio", "speech"],
    },
    {
        "id": "models",
        "label": "New models & releases",
        "color": "#0C447C",
        "glyph": "ti-package",
        "keywords": ["we release", "we introduce", "introducing", "open-source",
                     "open source", "model release", "weights", "checkpoint",
                     "outperforms", "state-of-the-art", "sota", "frontier model",
                     "billion parameter", "b parameter"],
    },
    {
        "id": "training",
        "label": "Training & architecture",
        "color": "#3B6D11",
        "glyph": "ti-adjustments",
        "keywords": ["pretrain", "fine-tun", "finetun", "rlhf", "reinforcement learning",
                     "mixture-of-experts", "mixture of experts", "moe", "transformer",
                     "attention", "scaling law", "optimizer", "loss function"],
    },
    {
        "id": "general",
        "label": "General AI",
        "color": "#5F5E5A",
        "glyph": "ti-sparkles",
        "keywords": [],  # catch-all
    },
]

# ---------------------------------------------------------------------------
# 4. Sensational / "big news" detection
# ---------------------------------------------------------------------------
# Items whose title hits these get a "Hot" flag and are eligible for the hero
# slot. Tuned toward big releases and dramatic claims.
HOT_SIGNALS = [
    "breakthrough", "first ever", "world's first", "record", "fastest",
    "launches", "launch", "releases", "unveils", "announces", "introducing",
    "outperforms", "beats gpt", "state-of-the-art", "sota", "open-sources",
    "billion", "raises", "acquires", "shuts down", "banned",
]

# Companies worth flagging by name (adds a small company chip).
WATCHED_ORGS = [
    "openai", "google", "deepmind", "anthropic", "meta", "microsoft",
    "nvidia", "mistral", "cohere", "stability", "hugging face", "xai",
    "alibaba", "deepseek", "qwen", "tencent",
]

# ---------------------------------------------------------------------------
# 5. General settings
# ---------------------------------------------------------------------------
FETCH_WINDOW_DAYS = 7      # only ingest items newer than this per run
ARCHIVE_YEARS = 5          # prune anything older than this from the DB
TODAY_WINDOW_DAYS = 3      # what the "Today" view considers current
ARCHIVE_PAGE_SIZE = 40     # items per page in the archive view
SITE_TITLE = "AI digest"
SITE_TAGLINE = "Papers, releases, and research, refreshed daily"
