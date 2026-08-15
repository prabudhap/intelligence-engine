from fastapi import APIRouter, Query, HTTPException
from app.database import db

router = APIRouter(prefix="/api")

def handle_db_exception(e: Exception):
    err_str = str(e).lower()
    if any(k in err_str for k in ["connect", "connection", "winerror", "refused", "offline", "unreachable"]):
        raise HTTPException(
            status_code=503,
            detail="Neo4j database is offline. Please start Docker / Neo4j container at bolt://localhost:7687."
        )
    raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations")
def get_organizations():
    try:
        orgs = db.get_organizations()
        return {"organizations": orgs}
    except Exception as e:
        handle_db_exception(e)

@router.get("/stats")
def get_stats(org: str = Query(..., description="Organization workspace name")):
    try:
        stats = db.get_stats(org)
        return stats
    except Exception as e:
        handle_db_exception(e)

@router.get("/recent")
def get_recent(org: str = Query(..., description="Organization workspace name")):
    try:
        articles = db.get_recent_articles(org)
        return {"articles": articles}
    except Exception as e:
        handle_db_exception(e)

@router.get("/graph")
def get_graph(org: str = Query(..., description="Organization workspace name")):
    try:
        graph_data = db.get_graph_data(org)
        return graph_data
    except Exception as e:
        handle_db_exception(e)

@router.get("/path")
def get_shortest_path(
    source: str = Query(..., description="Source node name or title"),
    target: str = Query(..., description="Target node name or title"),
    org: str = Query("Default", description="Organization workspace name")
):
    try:
        path_data = db.get_shortest_path(source, target, org)
        return path_data
    except Exception as e:
        handle_db_exception(e)
