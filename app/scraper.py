import logging
import random
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("uvicorn.error")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def scrape_article(url: str) -> dict:
    """
    Fetches an article URL, parses the HTML, and returns the title and body text.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    logger.info(f"🕸️ Attempting to scrape URL: {url}")
    
    try:
        # Use httpx with redirect follow and a 10s timeout
        with httpx.Client(headers=headers, follow_redirects=True, timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            html_content = response.text
    except Exception as e:
        logger.error(f"❌ Failed to fetch URL {url}: {e}")
        raise ValueError(f"Failed to fetch content from URL: {e}")
        
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Try to find the article title
        title = ""
        title_tags = [
            ("h1", {}),
            ("title", {}),
            ("meta", {"property": "og:title"}),
            ("meta", {"name": "twitter:title"})
        ]
        
        for tag_name, attrs in title_tags:
            tag = soup.find(tag_name, attrs)
            if tag:
                if tag_name == "meta":
                    title = tag.get("content", "").strip()
                else:
                    title = tag.get_text().strip()
                if title:
                    break
                    
        if not title:
            title = url  # Fallback to URL
            
        # 2. Extract article body paragraphs
        # Exclude elements that typically contain navigation, ads, headers, footers, scripts, styles, iframes
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
            element.decompose()
            
        # Try to locate common article container wrappers
        content_container = None
        container_candidates = [
            ("article", {}),
            ("main", {}),
            ("div", {"class": "post-content"}),
            ("div", {"class": "entry-content"}),
            ("div", {"class": "article-body"}),
            ("div", {"id": "article-body"}),
            ("div", {"class": "story-body"}),
        ]
        
        for tag_name, attrs in container_candidates:
            container = soup.find(tag_name, attrs)
            if container:
                # Ensure the container has actual paragraph elements
                if len(container.find_all("p")) >= 2:
                    content_container = container
                    break
                    
        search_root = content_container if content_container else soup
        
        # Fetch all paragraphs inside the search root
        paragraphs = search_root.find_all("p")
        text_blocks = []
        for p in paragraphs:
            text = p.get_text().strip()
            # Filter out very short texts which are usually cookie notices or button labels
            if len(text) > 30:
                text_blocks.append(text)
                
        body = "\n\n".join(text_blocks)
        
        # Fallback to meta-description if body is empty or too short
        if not body:
            meta_desc = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
            if meta_desc:
                body = meta_desc.get("content", "").strip()
                
        if not body:
            # Fallback: grab all text if no paragraphs were found
            body = soup.get_text(separator="\n\n").strip()
            
        # Limit text length to prevent context issues (e.g. max 15000 chars)
        if len(body) > 15000:
            body = body[:15000] + "\n\n[Content Truncated...]"
            
        logger.info(f"🎉 Successfully scraped title: '{title}' ({len(body)} characters)")
        return {
            "title": title,
            "body": body
        }
    except Exception as e:
        logger.error(f"❌ Failed to parse page content for {url}: {e}")
        raise ValueError(f"Failed to parse page content: {e}")
