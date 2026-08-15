import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core import logger, bg_executor
from app.database import db
from app.extractors import run_google_news_ingestion
from app.api import graph_router, ingestion_router

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

# Include Routers
app.include_router(graph_router)
app.include_router(ingestion_router)

# Mount static files folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve Frontend Index at the root
@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")