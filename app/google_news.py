import xml.etree.ElementTree as ET
import httpx
import logging
from app.scraper import scrape_article
from app.nlp import extract_entities
from app.database import Database

logger = logging.getLogger("uvicorn.error")

def parse_google_news_feed() -> list:
    url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    logger.info("📡 Fetching Google News RSS feed...")
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        
        articles = []
        for item in root.findall(".//item")[:20]:
            title_el = item.find("title")
            title = title_el.text if title_el is not None else "Untitled"
            
            link_el = item.find("link")
            link = link_el.text if link_el is not None else ""
            
            pub_date_el = item.find("pubDate")
            pub_date = pub_date_el.text if pub_date_el is not None else None
            
            if title and link:
                articles.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date
                })
        logger.info(f"🎉 Successfully parsed {len(articles)} articles from RSS feed.")
        return articles
    except Exception as e:
        logger.error(f"❌ Failed to retrieve/parse Google News RSS: {e}", exc_info=True)
        return []

def run_google_news_ingestion():
    """
    Scrapes the top 20 Google News articles, processes them using the NLP pipeline,
    and stores them under the 'Google News' workspace in Neo4j.
    """
    logger.info("🚀 Starting Google News ingestion worker...")
    db = Database()
    articles = parse_google_news_feed()
    
    success_count = 0
    for idx, art in enumerate(articles):
        title = art["title"]
        link = art["link"]
        pub_date = art["pub_date"]
        
        logger.info(f"({idx+1}/{len(articles)}) Processing Google News article: '{title}'")
        try:
            # Scrape content
            scraped = scrape_article(link)
            body_text = scraped["body"]
            
            # If title from scraping is empty, fallback to RSS title
            scraped_title = scraped["title"] if scraped["title"] and scraped["title"] != link else title
            
            # Extract entities
            entities = extract_entities(body_text)
            
            # Save to Neo4j database
            db.save_intelligence(
                org_name="Google News",
                title=scraped_title,
                entities=entities,
                body=body_text,
                pub_date=pub_date,
                url=scraped.get("url", link)
            )
            success_count += 1
            logger.info(f"✅ Successfully ingested: {scraped_title}")
        except Exception as e:
            logger.error(f"⚠️ Failed to ingest article '{title}': {e}")
            
    db.close()
    logger.info(f"🏁 Finished Google News ingestion. Successfully ingested {success_count}/{len(articles)} articles.")
    return success_count
