# OSINT Intelligence Engine 🕸️🤖

A technical blueprint and implementation of an automated Open Source Intelligence (OSINT) pipeline. It scrapes web articles, decodes publisher redirects, extracts named entities and sentiment via NLP, tracks real-time stock market metrics for corporate entities, constructs a temporal graph hierarchy, and maps network relationships in Neo4j.

---

## 🎯 Rebuilding from Scratch: System Mental Model

To understand or rebuild this engine from scratch, follow its core pipeline stages:

1. **Ingestion & Redirect Resolution:** Web scraping with rotated User-Agents combined with Google News internal `batchexecute` URL decoding (`garturlreq` RPC) to resolve raw publisher URLs.
2. **NLP Extraction Engine:** Named Entity Recognition (`PERSON`, `ORG` ➔ `Company`, `GPE` ➔ `Location`) using spaCy (`en_core_web_sm`), corporate suffix normalization (`Inc.`, `LLC`, `Corp.`, `PLC`, `AG`, `Group`, `Holdings`), domain topic classification (`Technology`, `Finance`, `Geopolitics`, `Defense`, `Healthcare`), and financial/security sentiment analysis.
3. **Stock Quote & Financial Analytics:** Real-time ticker symbol resolution and stock price metric retrieval via Yahoo Finance API with 60-second TTL quote caching and automated memory pruning (`prune_expired_cache`).
4. **Paragraph Proximity Engine:** Grouping and linking entity relationships mentioned within the exact same paragraph (`\n\n`) to prevent global network false positives.
5. **Temporal Hierarchy Engine:** Constructing a time tree (`Year` ➔ `Month` ➔ `Week` ➔ `Day` ➔ `TimePeriod` ➔ `Article`) linked to 6-hour interval bins for time-sliced graph queries.
6. **Graph Query & Vis.js Pathfinder UI:** High-speed Cypher queries (<415ms), shortest-path calculation (up to 6 hops), financial analytics overlays, and evidence extraction for dashboard visualizations.

---

## 🏗️ System Architecture & Component Mapping

```mermaid
graph TD
    User([User / Browser]) -->|REST API / Dashboard| API[FastAPI Application: app.api]
    
    subgraph Data Pipeline Components
        API -->|Scrape Request| Scraper[Scraper & Google Redirect Resolver: app.extractors.scraper]
        Scraper -->|Extracted Text| NLP[NLP Engine: app.nlp]
        NLP -->|Entities, Topic, Sentiment| DB[Neo4j Client & Cypher Repository: app.database]
        DB -->|Temporal Tree Builder| Temporal[Temporal Engine: app.database.temporal]
        API -->|Company Quote Lookup| Stock[Stock Quote & Ticker Resolver: app.services.stock_service]
    end
    
    subgraph Background Workers
        Cron[AsyncIO Scheduler] -->|Every 6h| NewsWorker[Google News RSS Sync: app.extractors.google_news]
        NewsWorker -->|Scrape & Pipeline| Scraper
        DB -->|Trigger Enrichment| WebEnrich[Open Web Search: app.extractors.enrichment]
        WebEnrich -->|Context Articles| Scraper
    end

    DB -->|Cypher Transactions| Neo4j[(Neo4j Graph Database)]
```

---

## 🧩 Key Modules & Responsibilities

| Module | Location | Purpose / How to Rebuild |
| :--- | :--- | :--- |
| **API Layer** | `app/api/` | FastAPI routers (`graph.py`, `ingestion.py`, `auth.py`) with `X-API-Key` security & 503 DB offline handlers. |
| **Scraper & Resolver** | `app/extractors/scraper.py` | BeautifulSoup article parser, SSRF domain protection, & Google News `batchexecute` RPC (`garturlreq`) decoder. |
| **NLP Pipeline** | `app/nlp/` | spaCy model loader (`model.py`), topic classification (`classification.py`), suffix stripper (`text_processing.py`). |
| **Stock Market Service** | `app/services/stock_service.py` | Ticker symbol resolver, Yahoo Finance real-time quote fetcher, & 60s TTL memory-pruned cache. |
| **Temporal Engine** | `app/database/temporal.py` | Date parser building `Year`/`Month`/`Week`/`Day`/`TimePeriod` IDs and paragraph context matchers. |
| **Graph Repository** | `app/database/repository.py` | Cypher transaction methods for node batching, graph payloads, entity deduplication, and shortest paths. |
| **Background Sync** | `app/extractors/` | `google_news.py` for 6h RSS crawls; `enrichment.py` for web searching top company entities. |

---

## 📊 Neo4j Graph Database Schema

If recreating the graph database, enforce the following node types and Cypher relationships:

### Node Labels & Unique Constraints
* `Organization` (`name` - Unique) — Workspace container
* `Article` (`title` - Unique, `url`, `body`, `category`, `sentiment`, `created_at`)
* `Person` (`name` - Unique), `Company` (`name` - Unique), `Location` (`name` - Unique)
* `Year` (`id`), `Month` (`id`), `Week` (`id`), `Day` (`id`), `TimePeriod` (`id`)

### Relationship Schema
```cypher
(:Article)-[:UNDER_WORKSPACE]->(:Organization)
(:Person|Company|Location)-[:MENTIONED_IN]->(:Article)
(:Person)-[:INDIRECTLY_INVOLVED_WITH]->(:Company)  // Linked via paragraph proximity
(:Person)-[:LOCATED_IN]->(:Location)               // Linked via paragraph proximity
(:TimePeriod)-[:HAS_ARTICLE]->(:Article)
(:Year)-[:HAS_MONTH]->(:Month)-[:HAS_WEEK]->(:Week)-[:HAS_DAY]->(:Day)-[:HAS_PERIOD]->(:TimePeriod)
```

---

## 🚀 Quick Start & Deployment Setup

### 1. Run full stack via Docker Compose
```bash
docker compose up --build -d
```
* **Dashboard:** `http://localhost:8000`
* **Swagger API Docs:** `http://localhost:8000/docs`
* **Neo4j Console:** `http://localhost:7474` (User: `neo4j`, Password: `secure_password_123`)

> Includes built-in container health check on Neo4j (`cypher-shell`) to ensure backend startup delays until database readiness.

### 2. Local Development Setup
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 📂 Codebase Directory Layout

```text
intelligence-engine/
├── app/
│   ├── api/        # REST routers: /api/graph, /api/company-financials, /api/path, /api/stats
│   ├── core/       # Global config (env vars, ThreadPoolExecutor, logging)
│   ├── database/   # Neo4j singleton, Cypher repository, entity resolution & temporal tree builder
│   ├── extractors/ # Web scraper, Google News decoder, & background enrichment
│   ├── nlp/        # spaCy entity resolution, topic, & sentiment pipelines
│   ├── services/   # Stock market service (Yahoo Finance integration & ticker resolution)
│   ├── static/     # Front-end Vis.js dashboard, app.js logic, & CSS styling
│   └── main.py     # FastAPI application lifespan, scheduler, & router mounts
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```



