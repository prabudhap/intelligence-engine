import ipaddress
import json
import random
import socket
from urllib.parse import urlparse
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

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB max download size limit

BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def validate_url_safety(url: str) -> None:
    """
    Validates URL scheme and resolves hostname IP to prevent Server-Side Request Forgery (SSRF)
    targeting private internal networks, loopback addresses, or cloud metadata endpoints.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Invalid URL: URL must be a non-empty string.")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https URLs are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: Hostname could not be resolved.")

    try:
        ip_info = socket.getaddrinfo(hostname, None)
        for family, socktype, proto, canonname, sockaddr in ip_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for blocked in BLOCKED_NETWORKS:
                if ip_obj in blocked:
                    raise ValueError(f"Access to private/internal IP address '{ip_str}' is forbidden for security.")
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve hostname '{hostname}': {e}")

def fetch_url_content_safely(url: str, headers: dict, timeout: float = 10.0) -> str:
    """
    Fetches URL content safely enforcing SSRF checks, max byte limits, and timeouts.
    """
    validate_url_safety(url)

    with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()

            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise ValueError(f"Response size exceeds maximum allowed limit ({MAX_RESPONSE_BYTES // (1024*1024)}MB).")

            downloaded_bytes = bytearray()
            for chunk in response.iter_bytes(chunk_size=8192):
                downloaded_bytes.extend(chunk)
                if len(downloaded_bytes) > MAX_RESPONSE_BYTES:
                    raise ValueError(f"Download size exceeded maximum allowed limit ({MAX_RESPONSE_BYTES // (1024*1024)}MB).")

            return downloaded_bytes.decode(response.encoding or "utf-8", errors="replace")

def resolve_google_news_url(url: str, user_agent: str) -> str:
    """
    Resolves the original publisher URL from a Google News redirect URL.
    """
    try:
        validate_url_safety(url)
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
    Enforces SSRF domain validation and response byte streaming limits.
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
        html_content = fetch_url_content_safely(url, headers=headers, timeout=10.0)
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
