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
    "cs.RO",      # robotics
    "cs.SE",      # software engineering / agents
    "eess.SP",    # speech & audio
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

    # ------------------- Company Research -------------------

    {
        "label": "Google DeepMind",
        "rss": "https://deepmind.google/blog/rss.xml",
        "site": "https://deepmind.google/discover/blog/",
        "kind": "company",
    },

    {
        "label": "Google AI",
        "rss": "https://blog.google/technology/ai/rss/",
        "site": "https://blog.google/technology/ai/",
        "kind": "company",
    },

    {
        "label": "OpenAI",
        "rss": "https://openai.com/news/rss.xml",
        "site": "https://openai.com/news/",
        "kind": "company",
    },

    {
        "label": "Microsoft Research",
        "rss": "https://www.microsoft.com/en-us/research/feed/",
        "site": "https://www.microsoft.com/en-us/research/blog/",
        "kind": "company",
    },

    {
        "label": "Meta AI",
        "rss": "https://ai.meta.com/blog/rss/",
        "site": "https://ai.meta.com/blog/",
        "kind": "company",
    },

    {
        "label": "NVIDIA Developer",
        "rss": "https://developer.nvidia.com/blog/feed",
        "site": "https://developer.nvidia.com/blog/",
        "kind": "company",
    },

    {
        "label": "AWS ML Blog",
        "rss": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "site": "https://aws.amazon.com/blogs/machine-learning/",
        "kind": "company",
    },

    # ------------------- News -------------------

    {
        "label": "VentureBeat AI",
        "rss": "https://venturebeat.com/category/ai/feed/",
        "site": "https://venturebeat.com/ai/",
        "kind": "news",
    },

    {
        "label": "TechCrunch AI",
        "rss": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "site": "https://techcrunch.com/category/artificial-intelligence/",
        "kind": "news",
    },

    {
        "label": "MIT Tech Review",
        "rss": "https://www.technologyreview.com/feed/",
        "site": "https://www.technologyreview.com/topic/artificial-intelligence/",
        "kind": "news",
    },

    {
        "label": "Ars Technica",
        "rss": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "site": "https://arstechnica.com/ai/",
        "kind": "news",
    },

    # ------------------- Blogs -------------------

    {
        "label": "The Batch",
        "rss": "https://www.deeplearning.ai/the-batch/feed/",
        "site": "https://www.deeplearning.ai/the-batch/",
        "kind": "blog",
    },

    {
        "label": "MarkTechPost",
        "rss": "https://www.marktechpost.com/feed/",
        "site": "https://www.marktechpost.com/",
        "kind": "blog",
    },
]

TOPIC_AREAS = [
    {
        "id":"graphics","label":"Graphics & rendering","color":"#D85A30","glyph":"ti-cube",
        "keywords":["nvidia","rendering","render","graphics","nerf","gaussian splat","ray tracing","shader","3d reconstruction","dlss","texture synthesis"]
    },
    {
        "id":"quantum","label":"Quantum","color":"#7F77DD","glyph":"ti-atom",
        "keywords":["quantum","qubit","qaoa","variational quantum","quantum machine learning","quantum circuit"]
    },
    {
        "id":"hallucination","label":"Hallucination & reliability","color":"#D4537E","glyph":"ti-alert-triangle",
        "keywords":["hallucinat","factual","faithfulness","truthful","calibration","uncertainty","reliability","grounding"]
    },
    {
        "id":"cognition","label":"Cognition & reasoning","color":"#1D9E75","glyph":"ti-brain",
        "keywords":["cognit","reasoning","chain-of-thought","planning","world model","metacognit","self-reflect","deliberat"]
    },
    {
        "id":"knowledge_graphs","label":"Knowledge graphs & retrieval","color":"#185FA5","glyph":"ti-share",
        "keywords":["knowledge graph","knowledge base","retrieval-augmented","rag ","graph neural","entity linking","ontology","semantic"]
    },
    {
        "id":"systems","label":"Latency, serving & systems","color":"#854F0B","glyph":"ti-bolt",
        "keywords":["latency","throughput","kv cache","speculative decod","quantiz","flashattention","serving","batching","udp","rdma","networking"]
    },
    {
        "id":"agentic","label":"Agentic AI","color":"#146C94","glyph":"ti-route",
        "keywords":["agentic","workflow","planner","memory","reflection","tool orchestration","mcp","a2a","acp","multi-agent"]
    },
    {
        "id":"evaluation","label":"Evaluation & Benchmarks","color":"#8E44AD","glyph":"ti-chart-bar",
        "keywords":["benchmark","evaluation","eval","arena","reward model","judge","verification","leaderboard"]
    },
    {
        "id":"infrastructure","label":"AI Infrastructure","color":"#B35C00","glyph":"ti-server",
        "keywords":["gpu","cuda","h100","b200","tpu","compiler","runtime","vllm","tensorrt","inference engine"]
    },
    {
        "id":"robotics","label":"Robotics","color":"#287233","glyph":"ti-armchair-2",
        "keywords":["robotics","embodied","navigation","manipulation","policy learning"]
    },
    {
        "id":"security","label":"AI Safety & Security","color":"#B22222","glyph":"ti-shield-lock",
        "keywords":["alignment","jailbreak","red team","red teaming","adversarial","safety"]
    },
    {
        "id":"healthcare","label":"Healthcare AI","color":"#00897B","glyph":"ti-heartbeat",
        "keywords":["clinical","medical","drug discovery","oncology","patient","bioinformatics","healthcare"]
    },
    {
        "id":"multimodal","label":"Multimodal & vision","color":"#993C1D","glyph":"ti-eye",
        "keywords":["multimodal","vision-language","vlm","image generation","video generation","diffusion","speech","audio"]
    },
    {
        "id":"models","label":"New models & releases","color":"#0C447C","glyph":"ti-package",
        "keywords":["introducing","release","weights","checkpoint","state-of-the-art","frontier model","billion parameter"]
    },
    {
        "id":"training","label":"Training & architecture","color":"#3B6D11","glyph":"ti-adjustments",
        "keywords":["pretrain","fine-tun","rlhf","reinforcement learning","mixture-of-experts","moe","transformer","attention","optimizer"]
    },
    {
        "id":"general","label":"General AI","color":"#5F5E5A","glyph":"ti-sparkles","keywords":[]
    }
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
