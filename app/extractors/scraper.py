import random
import json
import httpx
from bs4 import BeautifulSoup

from app.core import logger

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def resolve_google_news_url(url: str, user_agent: str) -> str:
    """
    Resolves the original publisher URL from a Google News redirect URL.
    """
    try:
        with httpx.Client(headers={"User-Agent": user_agent}, follow_redirects=True, timeout=10.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            c_wiz = soup.select_one('c-wiz[data-p]')
            if not c_wiz:
                logger.warning(f"c-wiz not found for Google News URL redirect: {url}")
                return url
            data_p = c_wiz.get('data-p')
            if not data_p:
                logger.warning(f"data-p not found for Google News URL redirect: {url}")
                return url
                
            obj = json.loads(data_p.replace('%.@.', '["garturlreq",'))
            payload_data = obj[:-6] + obj[-2:]
            payload = {
                'f.req': json.dumps([[["Fbv4je", json.dumps(payload_data), "null", "generic"]]])
            }
            
            api_url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            response = client.post(api_url, headers={
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8'
            }, data=payload)
            response.raise_for_status()
            
            response_text = response.text
            if response_text.startswith(")]}'"):
                response_text = response_text[4:]
            
            data = json.loads(response_text)
            array_string = data[0][2]
            final_url = json.loads(array_string)[1]
            logger.info(f"🔗 Successfully resolved Google News URL redirect to: {final_url}")
            return final_url
    except Exception as e:
        logger.error(f"❌ Failed to resolve Google News URL redirect: {e}")
        return url

def _extract_article_title(soup: BeautifulSoup, fallback_url: str) -> str:
    """Extracts article title using meta tags and heading tags, falling back to URL."""
    title_tags = [
        ("h1", {}),
        ("title", {}),
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "twitter:title"})
    ]
    for tag_name, attrs in title_tags:
        tag = soup.find(tag_name, attrs)
        if tag:
            title = tag.get("content", "").strip() if tag_name == "meta" else tag.get_text().strip()
            if title:
                return title
    return fallback_url

def _extract_article_body(soup: BeautifulSoup, max_length: int = 15000) -> str:
    """Extracts paragraph content from main article containers, falling back to meta descriptions."""
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
        element.decompose()
        
    container_candidates = [
        ("article", {}),
        ("main", {}),
        ("div", {"class": "post-content"}),
        ("div", {"class": "entry-content"}),
        ("div", {"class": "article-body"}),
        ("div", {"id": "article-body"}),
        ("div", {"class": "story-body"}),
    ]
    
    content_container = None
    for tag_name, attrs in container_candidates:
        container = soup.find(tag_name, attrs)
        if container and len(container.find_all("p")) >= 2:
            content_container = container
            break
                
    search_root = content_container if content_container else soup
    text_blocks = [p.get_text().strip() for p in search_root.find_all("p") if len(p.get_text().strip()) > 30]
    body = "\n\n".join(text_blocks)
    
    if not body:
        meta_desc = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
        if meta_desc:
            body = meta_desc.get("content", "").strip()
            
    if not body:
        body = soup.get_text(separator="\n\n").strip()
        
    if len(body) > max_length:
        body = body[:max_length] + "\n\n[Content Truncated...]"
        
    return body

def scrape_article(url: str) -> dict:
    """
    Fetches an article URL, parses the HTML, and returns the title and body text.
    """
    user_agent = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    # Resolve Google News redirect if applicable
    if "news.google.com" in url:
        logger.info(f"📡 Resolving Google News redirect URL: {url}")
        url = resolve_google_news_url(url, user_agent)
        
    logger.info(f"🕸️ Attempting to scrape URL: {url}")
    
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            html_content = response.text
    except Exception as e:
        logger.error(f"❌ Failed to fetch URL {url}: {e}")
        raise ValueError(f"Failed to fetch content from URL: {e}")
        
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        title = _extract_article_title(soup, url)
        body = _extract_article_body(soup)
            
        logger.info(f"🎉 Successfully scraped title: '{title}' ({len(body)} characters)")
        return {
            "title": title,
            "body": body,
            "url": url
        }
    except Exception as e:
        logger.error(f"❌ Failed to parse page content for {url}: {e}")
        raise ValueError(f"Failed to parse page content: {e}")
