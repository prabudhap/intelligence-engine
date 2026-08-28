from fastapi import APIRouter, Query, HTTPException, Depends
from app.database import db
from app.api.auth import verify_api_key

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
def get_graph(
    org: str = Query(..., description="Organization workspace name"),
    limit: int = Query(30, ge=1, le=200, description="Max articles to fetch in graph view"),
    include_time_tree: bool = Query(False, description="Include time hierarchy tree nodes")
):
    try:
        graph_data = db.get_graph_data(org, limit=limit, include_time_tree=include_time_tree)
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

@router.post("/consolidate", dependencies=[Depends(verify_api_key)])
def consolidate_workspace_entities(
    org: str = Query("Default", description="Organization workspace name")
):
    try:
        res = db.deduplicate_entities(org)
        return res
    except Exception as e:
        handle_db_exception(e)

@router.post("/vacuum", dependencies=[Depends(verify_api_key)])
def vacuum_database(
    org: str = Query("Default", description="Organization workspace name"),
    prune_cooccurrences: bool = Query(False, description="Whether to prune 1-off transient co-occurrence edges")
):
    try:
        res = db.vacuum_database(org, prune_cooccurrences=prune_cooccurrences)
        return res
    except Exception as e:
        handle_db_exception(e)

from app.services import fetch_stock_quote

@router.get("/space-stats")
def get_space_stats(
    org: str = Query("Default", description="Organization workspace name")
):
    try:
        stats = db.get_space_stats(org)
        return stats
    except Exception as e:
        handle_db_exception(e)

@router.get("/company-financials")
def get_company_financials(
    company: str = Query(..., description="Company or Organization entity name"),
    org: str = Query("Default", description="Organization workspace name")
):
    try:
        quote = fetch_stock_quote(company)
        
        articles = db.get_company_related_articles(company, org)
        
        pos_count = sum(1 for a in articles if a.get("sentiment") == "Positive")
        neg_count = sum(1 for a in articles if a.get("sentiment") == "Negative")
        neu_count = sum(1 for a in articles if a.get("sentiment") not in ["Positive", "Negative"])
        total_arts = len(articles)
        
        pos_pct = round((pos_count / total_arts * 100), 1) if total_arts > 0 else 0.0
        neg_pct = round((neg_count / total_arts * 100), 1) if total_arts > 0 else 0.0
        neu_pct = round((neu_count / total_arts * 100), 1) if total_arts > 0 else 0.0
        
        return {
            "stock_quote": quote,
            "sentiment_summary": {
                "total_articles": total_arts,
                "positive": pos_count,
                "negative": neg_count,
                "neutral": neu_count,
                "positive_pct": pos_pct,
                "negative_pct": neg_pct,
                "neutral_pct": neu_pct
            },
            "articles": articles
        }
    except Exception as e:
        handle_db_exception(e)


