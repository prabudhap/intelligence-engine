import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("uvicorn.error")

def scrape_article(url: str) -> dict:
    """
    Fetches an article URL, parses the HTML, and returns the title and body text.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
        # Common news tags for titles
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
        # Exclude elements that typically contain navigation, ads, headers, footers, scripts, styles
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()
            
        # Fetch all paragraphs
        paragraphs = soup.find_all("p")
        text_blocks = []
        for p in paragraphs:
            text = p.get_text().strip()
            # Filter out very short texts which are usually cookie notices or button labels
            if len(text) > 30:
                text_blocks.append(text)
                
        body = "\n\n".join(text_blocks)
        
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
