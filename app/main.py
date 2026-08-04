import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.nlp import extract_entities
from app.database import Database
from app.scraper import scrape_article

logger = logging.getLogger("uvicorn.error")

# Instantiate DB driver
db = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup phase
    logger.info("Starting up OSINT Intelligence Engine API...")
    try:
        db.setup_constraints()
        logger.info("Successfully initialized Neo4j unique constraints & indexes.")
    except Exception as e:
        logger.error(f"Failed to initialize database constraints: {e}")
    yield
    # Shutdown phase
    logger.info("Shutting down OSINT Intelligence Engine API...")
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
def pipeline_worker(org: str, title: str, body: str):
    try:
        entities = extract_entities(body)
        db.save_intelligence(org, title, entities)
        logger.info(f"🎉 Successfully mapped node networks for: {title} inside workspace: {org}")
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
    target: str = Query(..., description="Target node name or title")
):
    try:
        path_data = db.get_shortest_path(source, target)
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
        background_tasks.add_task(pipeline_worker, payload.org, title, body)
        
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

# Mount static files folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve Frontend Index at the root
@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")