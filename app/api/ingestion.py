from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core import logger, bg_executor
from app.database import db
from app.nlp import extract_entities
from app.extractors.scraper import scrape_article
from app.extractors.google_news import run_google_news_ingestion
from app.extractors.enrichment import run_web_enrichment

router = APIRouter()

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
            bg_executor.submit(run_web_enrichment, org, enrich_targets)
    except Exception as e:
        logger.error(f"❌ Failed to process article '{title}' in workspace '{org}': {e}", exc_info=True)

# API Endpoints
@router.post("/api/scrape")
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
            "message": "Successfully scraped. Ingestion started in background.",
            "title": title
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/process-news")
def process_news(article: ArticleInput, background_tasks: BackgroundTasks):
    background_tasks.add_task(pipeline_worker, article.org, article.title, article.body)
    return {"status": "queued", "message": "Article layout extraction started inside Docker."}

@router.post("/api/cron/google-news")
def trigger_google_news(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(run_google_news_ingestion)
        return {
            "status": "queued",
            "message": "Google News ingestion triggered in background task."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
