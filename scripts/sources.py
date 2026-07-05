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
        "keywords":["nvidia","rendering","render","graphics","nerf","gaussian splat","ray tracing","shader","3d reconstruction","dlss","texture synthesis"],
        "description":[
            "Computer graphics research: rendering, ray tracing, and shading.",
            "Neural rendering such as NeRF and Gaussian splatting.",
            "GPU-accelerated real-time rendering pipelines and 3D reconstruction.",
        ],
    },
    {
        "id":"quantum","label":"Quantum","color":"#7F77DD","glyph":"ti-atom",
        "keywords":["quantum","qubit","qaoa","variational quantum","quantum machine learning","quantum circuit"],
        "description":[
            "Quantum computing research, qubits, and quantum circuits.",
            "Quantum machine learning and variational quantum algorithms.",
        ],
    },
    {
        "id":"hallucination","label":"Hallucination & reliability","color":"#D4537E","glyph":"ti-alert-triangle",
        "keywords":["hallucinat","factual","faithfulness","truthful","calibration","uncertainty","reliability","grounding"],
        "description":[
            "Language model hallucination, factuality, and truthfulness.",
            "Model calibration, uncertainty estimation, and grounding of generated text.",
        ],
    },
    {
        "id":"cognition","label":"Cognition & reasoning","color":"#1D9E75","glyph":"ti-brain",
        "keywords":["cognit","reasoning","chain-of-thought","planning","world model","metacognit","self-reflect","deliberat"],
        "description":[
            "Machine reasoning, planning, and chain-of-thought.",
            "World models, metacognition, and self-reflective AI systems.",
        ],
    },
    {
        "id":"knowledge_graphs","label":"Knowledge graphs & retrieval","color":"#185FA5","glyph":"ti-share",
        "keywords":["knowledge graph","knowledge base","retrieval-augmented","rag ","graph neural","entity linking","ontology","semantic"],
        "description":[
            "Knowledge graphs, ontologies, and entity linking.",
            "Retrieval-augmented generation and graph neural networks for search.",
        ],
    },
    {
        "id":"systems","label":"Latency, serving & systems","color":"#854F0B","glyph":"ti-bolt",
        "keywords":["latency","throughput","kv cache","speculative decod","quantiz","flashattention","serving","batching","udp","rdma","networking"],
        "description":[
            "Model serving systems: latency, throughput, and batching.",
            "Inference optimization: KV cache, quantization, speculative decoding.",
            "Networking and transport protocols for distributed systems.",
        ],
    },
    {
        "id":"agentic","label":"Agentic AI","color":"#146C94","glyph":"ti-route",
        "keywords":["agentic","workflow","planner","memory","reflection","tool orchestration","mcp","a2a","acp","multi-agent"],
        "description":[
            "Agentic AI systems: planners, tool use, and multi-agent workflows.",
            "Agent memory, reflection, and orchestration protocols like MCP.",
        ],
    },
    {
        "id":"evaluation","label":"Evaluation & Benchmarks","color":"#8E44AD","glyph":"ti-chart-bar",
        "keywords":["benchmark","evaluation","eval","arena","reward model","judge","verification","leaderboard"],
        "description":[
            "Evaluation methodology, benchmarks, and leaderboards for AI models.",
            "LLM-as-judge, reward models, and verification techniques.",
        ],
    },
    {
        "id":"infrastructure","label":"AI Infrastructure","color":"#B35C00","glyph":"ti-server",
        "keywords":["gpu","cuda","h100","b200","tpu","compiler","runtime","vllm","tensorrt","inference engine"],
        "description":[
            "AI hardware and infrastructure: GPUs, TPUs, and accelerators.",
            "Inference engines, compilers, and runtimes for machine learning.",
        ],
    },
    {
        "id":"robotics","label":"Robotics","color":"#287233","glyph":"ti-armchair-2",
        "keywords":["robotics","embodied","navigation","manipulation","policy learning"],
        "description":[
            "Robotics research: embodied agents, navigation, and manipulation.",
            "Policy learning for physical robots.",
        ],
    },
    {
        "id":"security","label":"AI Safety & Security","color":"#B22222","glyph":"ti-shield-lock",
        "keywords":["alignment","jailbreak","red team","red teaming","adversarial","safety"],
        "description":[
            "AI safety, alignment, and adversarial robustness.",
            "Jailbreaks, red-teaming, and security testing of AI models.",
        ],
    },
    {
        "id":"healthcare","label":"Healthcare AI","color":"#00897B","glyph":"ti-heartbeat",
        "keywords":["clinical","medical","drug discovery","oncology","patient","bioinformatics","healthcare"],
        "description":[
            "AI applied to healthcare, clinical medicine, and patient care.",
            "Drug discovery, oncology, and bioinformatics.",
        ],
    },
    {
        "id":"multimodal","label":"Multimodal & vision","color":"#993C1D","glyph":"ti-eye",
        "keywords":["multimodal","vision-language","vlm","image generation","video generation","diffusion","speech","audio"],
        "description":[
            "Multimodal and vision-language models.",
            "Image, video, and speech generation, including diffusion models.",
        ],
    },
    {
        "id":"models","label":"New models & releases","color":"#0C447C","glyph":"ti-package",
        "keywords":["introducing","release","weights","checkpoint","state-of-the-art","frontier model","billion parameter"],
        "description":[
            "Announcements of new AI model releases and open-weight checkpoints.",
            "Frontier model launches and state-of-the-art results.",
        ],
    },
    {
        "id":"training","label":"Training & architecture","color":"#3B6D11","glyph":"ti-adjustments",
        "keywords":["pretrain","fine-tun","rlhf","reinforcement learning","mixture-of-experts","moe","transformer","attention","optimizer"],
        "description":[
            "Model training: pretraining, fine-tuning, and RLHF.",
            "Neural network architecture: transformers, mixture-of-experts, optimizers.",
        ],
    },
    {
        "id":"general","label":"General AI","color":"#5F5E5A","glyph":"ti-sparkles","keywords":[],"description":["General artificial intelligence news."]
    }
]

# ---------------------------------------------------------------------------
# 3b. Semantic topic classification (sentence-embedding based)
# ---------------------------------------------------------------------------
# Replaces the pure keyword matcher above. Each TOPIC_AREA's "description"
# sentences are embedded and averaged into a centroid; every item is embedded
# once and assigned to whichever centroid (predefined OR a previously
# discovered dynamic topic) it's most similar to, above SEMANTIC_MATCH_THRESHOLD.
# Items that clear no centroid fall into "general" and become candidates for
# community detection in topics.discover_topics().
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Cosine similarity an item must clear against a class/topic centroid to be
# assigned to it. Lower = looser buckets, higher = more items land in "general".
SEMANTIC_MATCH_THRESHOLD = 0.38

# Community detection over the accumulated "general" pool, run every fetch.py
# pass (sentence_transformers.util.community_detection).
DYNAMIC_TOPIC_MIN_CLUSTER = 4       # min items before a cluster becomes a topic
DYNAMIC_TOPIC_THRESHOLD = 0.4      # cosine similarity within a discovered cluster
DYNAMIC_TOPIC_MERGE_THRESHOLD = 0.85  # merge a new cluster into an existing dynamic topic if this close

# Cap on how many "general"-bucket items discover_topics() clusters over per
# run (most recent first). Community detection is roughly O(n^2); this keeps
# each run fast even once the archive has accumulated years of "general"
# items. Raise it if you want deeper sweeps at the cost of run time.
DYNAMIC_TOPIC_POOL_CAP = 1500

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
ARCHIVE_YEARS = 1          # prune anything older than this from the DB
TODAY_WINDOW_DAYS = 3      # what the "Today" view considers current
WEEKLY_WINDOW_DAYS = 7     # what the "Weekly" view considers current
MAX_HEROES = 6             # how many hero cards the Today/Weekly carousel shows
ARCHIVE_PAGE_SIZE = 40     # items per page in the archive view
SITE_TITLE = "AI digest"
SITE_TAGLINE = "Papers, releases, and research, refreshed daily"
