import httpx
import urllib.parse

from app.core import logger
from app.extractors.rss_utils import parse_rss_items
from app.extractors.scraper import scrape_article
from app.nlp import extract_entities
from app.database import Database

def search_news_for_entity(entity_name: str) -> list:
    """
    Queries Google News Search RSS feed for a specific entity name, returning 
    the top 2 article details.
    """
    query = urllib.parse.quote(f'"{entity_name}"')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    logger.info(f"📡 Searching the web for context on entity: '{entity_name}'...")
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)
        resp.raise_for_status()
        return parse_rss_items(resp.content, limit=2)
    except Exception as e:
        logger.error(f"⚠️ Google News Search RSS failed for entity '{entity_name}': {e}")
        return []

def run_web_enrichment(org: str, entities: list[str]):
    """
    Asynchronously queries search engines for the top extracted entities, 
    scrapes secondary source documents, extracts additional relationships,
    and links them back to the active workspace.
    """
    logger.info(f"🕸️ Starting Open Web Enrichment Loop for: {entities}")
    db = Database()
    
    processed_urls = set()
    
    for entity in entities:
        search_results = search_news_for_entity(entity)
        if not search_results:
            continue
            
        for art in search_results:
            title = art["title"]
            link = art["link"]
            pub_date = art["pub_date"]
            
            if link in processed_urls:
                continue
            processed_urls.add(link)
            
            logger.info(f"🔗 Enrolling supporting article: '{title}' from web search...")
            try:
                scraped = scrape_article(link)
                body_text = scraped["body"]
                scraped_title = scraped["title"] if scraped["title"] and scraped["title"] != link else title
                
                result_entities = extract_entities(body_text)
                
                if "companies" not in result_entities:
                    result_entities["companies"] = []
                if entity not in result_entities["companies"] and entity not in result_entities.get("people", []) and entity not in result_entities.get("locations", []):
                    result_entities["companies"].append(entity)
                
                db.save_intelligence(
                    org_name=org,
                    title=f"[Enriched] {scraped_title}",
                    entities=result_entities,
                    body=body_text,
                    pub_date=pub_date,
                    url=scraped.get("url", link)
                )
                logger.info(f"✅ Successfully correlated enriched node: {scraped_title}")
            except Exception as e:
                logger.error(f"⚠️ Failed to process enriched context for '{title}': {e}")
                
    db.close()
    logger.info("🏁 Finished Web Enrichment Loop.")
