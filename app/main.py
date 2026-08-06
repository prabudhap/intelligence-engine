import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.nlp import extract_entities
from app.database import db
from app.scraper import scrape_article
from app.google_news import run_google_news_ingestion
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("uvicorn.error")

# Global background tasks executor
bg_executor = ThreadPoolExecutor(max_workers=4)

async def google_news_scheduler():
    logger.info("🕒 Starting Google News automatic scheduler (every 6 hours)...")
    # Wait 10 seconds before the first crawl on startup
    await asyncio.sleep(10)
    while True:
        try:
            logger.info("🕒 Scheduled task: Executing Google News ingestion...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(bg_executor, run_google_news_ingestion)
        except Exception as e:
            logger.error(f"❌ Error in scheduled Google News crawler: {e}", exc_info=True)
        logger.info("🕒 Google News scheduler sleeping for 6 hours...")
        await asyncio.sleep(6 * 3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup phase
    logger.info("Starting up OSINT Intelligence Engine API...")
    try:
        db.setup_constraints()
        logger.info("Successfully initialized Neo4j unique constraints & indexes.")
    except Exception as e:
        logger.error(f"Failed to initialize database constraints: {e}")
    
    # Start background scheduler task
    app.state.scheduler_task = asyncio.create_task(google_news_scheduler())
    
    yield
    # Shutdown phase
    logger.info("Shutting down OSINT Intelligence Engine API...")
    if hasattr(app.state, "scheduler_task"):
        app.state.scheduler_task.cancel()
    bg_executor.shutdown(wait=False)
    db.close()

app = FastAPI(title="OSINT Dockerized Intelligence Engine API", lifespan=lifespan)

# API Schemas
class ArticleInput(BaseModel):
    title: str
    body: str
    org: str = "Default"

class ScrapeInput(BaseModel):
    url: str
    org: str

# Helper pipeline worker
def pipeline_worker(org: str, title: str, body: str, url: str | None = None):
    try:
        entities = extract_entities(body)
        db.save_intelligence(org, title, entities, body, url=url)
        logger.info(f"🎉 Successfully mapped node networks for: {title} inside workspace: {org}")
        
        # Open Web Enrichment: Search the web for context on the top 3 companies
        companies = entities.get("companies", [])
        enrich_targets = [c for c in companies if c.lower() != "google news"][:3]
        if enrich_targets:
            logger.info(f"🔍 Enqueueing Open Web Enrichment for entities: {enrich_targets} inside workspace: {org}")
            from app.enrichment import run_web_enrichment
            bg_executor.submit(run_web_enrichment, org, enrich_targets)
    except Exception as e:
        logger.error(f"❌ Failed to process article '{title}' in workspace '{org}': {e}", exc_info=True)

# API Endpoints
@app.get("/api/organizations")
def get_organizations():
    try:
        orgs = db.get_organizations()
        return {"organizations": orgs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def get_stats(org: str = Query(..., description="Organization workspace name")):
    try:
        stats = db.get_stats(org)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recent")
def get_recent(org: str = Query(..., description="Organization workspace name")):
    try:
        articles = db.get_recent_articles(org)
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph")
def get_graph(org: str = Query(..., description="Organization workspace name")):
    try:
        graph_data = db.get_graph_data(org)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/path")
def get_shortest_path(
    source: str = Query(..., description="Source node name or title"),
    target: str = Query(..., description="Target node name or title"),
    org: str = Query("Default", description="Organization workspace name")
):
    try:
        path_data = db.get_shortest_path(source, target, org)
        return path_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scrape")
def process_scrape(payload: ScrapeInput, background_tasks: BackgroundTasks):
    try:
        # Perform scraper synchronously so we can return the scraped title to the UI
        scraped_data = scrape_article(payload.url)
        title = scraped_data["title"]
        body = scraped_data["body"]
        
        # Enqueue NLP & DB work in background
        background_tasks.add_task(pipeline_worker, payload.org, title, body, scraped_data.get("url", payload.url))
        
        return {
            "status": "queued",
            "message": f"Successfully scraped. Ingestion started in background.",
            "title": title
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/process-news")
def process_news(article: ArticleInput, background_tasks: BackgroundTasks):
    background_tasks.add_task(pipeline_worker, article.org, article.title, article.body)
    return {"status": "queued", "message": "Article layout extraction started inside Docker."}

@app.post("/api/cron/google-news")
def trigger_google_news(background_tasks: BackgroundTasks):
    try:
        from app.google_news import run_google_news_ingestion
        background_tasks.add_task(run_google_news_ingestion)
        return {
            "status": "queued",
            "message": "Google News ingestion triggered in background task."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve Frontend Index at the root
@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")