import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import httpx
from app.core import logger

# Pre-compiled regular expressions for maximum lookup performance
SUFFIX_CLEAN_RE = re.compile(
    r'\b(INC|LLC|LTD|CORP|CORPORATION|LIMITED|CO|COMPANY|PLC|AG|SA|NV|AB|GROUP|HOLDINGS|ENTERPRISES|TECHNOLOGIES)\b\.?$', 
    re.IGNORECASE
)
TRAILING_PUNCT_RE = re.compile(r'[\s,\.]+$')
RAW_TICKER_RE = re.compile(r'^[A-Z]{2,5}$')
TICKER_VALID_RE = re.compile(r'^[A-Z0-9\.\-]{1,10}$')

# In-memory TTL quote cache (60 seconds expiration)
QUOTE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 60.0

def prune_expired_cache(now: float | None = None) -> None:
    """Removes entries from QUOTE_CACHE that have passed their TTL."""
    current_time = now if now is not None else time.time()
    expired_keys = [
        k for k, (cached_time, _) in QUOTE_CACHE.items() 
        if current_time - cached_time >= CACHE_TTL_SECONDS
    ]
    for k in expired_keys:
        QUOTE_CACHE.pop(k, None)

def clear_quote_cache() -> None:
    """Clears the in-memory stock quote cache."""
    QUOTE_CACHE.clear()

def load_ticker_map(file_path: str | Path | None = None) -> Dict[str, str]:
    """Loads ticker symbol mapping dictionary from a JSON resource file."""
    path = Path(file_path) if file_path else Path(__file__).parent.parent / "resources" / "ticker_map.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read ticker_map.json resource file: {e}")
    return {}

TICKER_MAP = load_ticker_map()

def resolve_ticker_symbol(company_name: str) -> Optional[str]:
    """
    Resolves a company name string to a stock ticker symbol.
    Uses pre-compiled regexes, corporate suffix stripping, and length guards to prevent false positives.
    """
    if not company_name or not isinstance(company_name, str):
        return None
        
    clean = company_name.upper().strip()
    if not clean:
        return None
        
    # Strip common corporate suffixes for matching
    clean_base = SUFFIX_CLEAN_RE.sub('', clean).strip()
    clean_base = TRAILING_PUNCT_RE.sub('', clean_base).strip()
    
    if clean in TICKER_MAP:
        return TICKER_MAP[clean]
    if clean_base in TICKER_MAP:
        return TICKER_MAP[clean_base]
        
    # Partial substring search with minimum length guards (>= 4 chars)
    if len(clean_base) >= 4:
        for name_key, ticker in TICKER_MAP.items():
            if len(name_key) >= 4 and (name_key in clean_base or clean_base in name_key):
                return ticker
            
    # If the input looks like a raw 2-5 letter ticker symbol
    if RAW_TICKER_RE.match(clean_base):
        return clean_base
        
    return None

def fetch_stock_quote(company_name: str) -> Dict[str, Any]:
    """
    Fetches real-time USD stock price, previous close, and price change 
    from Yahoo Finance API for a company. Implements URL sanitization and 60-second TTL caching.
    """
    ticker = resolve_ticker_symbol(company_name)
    if not ticker or not TICKER_VALID_RE.match(ticker):
        return {
            "company_name": company_name,
            "ticker": None,
            "is_public": False,
            "message": "Private / Unlisted Entity"
        }

    # Check and prune 60-second in-memory quote cache
    now = time.time()
    prune_expired_cache(now)
    
    if ticker in QUOTE_CACHE:
        cached_time, cached_data = QUOTE_CACHE[ticker]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    safe_ticker = urllib.parse.quote(ticker.strip())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{safe_ticker}?interval=1d&range=2d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=5.0) as client:
            response = client.get(url)
            if response.status_code != 200:
                logger.warning(f"Yahoo Finance returned status {response.status_code} for ticker {ticker}")
                return {
                    "company_name": company_name,
                    "ticker": ticker,
                    "is_public": True,
                    "error": "Stock quote unavailable"
                }
                
            data = response.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return {
                    "company_name": company_name,
                    "ticker": ticker,
                    "is_public": True,
                    "error": "No market data found"
                }
                
            meta = result[0].get("meta", {})
            current_price = meta.get("regularMarketPrice")
            previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")
            currency = meta.get("currency", "USD")
            
            if current_price is None or previous_close is None:
                return {
                    "company_name": company_name,
                    "ticker": ticker,
                    "is_public": True,
                    "error": "Price data incomplete"
                }
                
            change_amount = current_price - previous_close
            percent_change = (change_amount / previous_close) * 100 if previous_close else 0.0
            
            quote_result = {
                "company_name": company_name,
                "ticker": ticker,
                "is_public": True,
                "currency": currency,
                "current_price": round(current_price, 2),
                "previous_close": round(previous_close, 2),
                "change_amount": round(change_amount, 2),
                "percent_change": round(percent_change, 2),
                "is_up": change_amount >= 0,
                "formatted_price": f"${current_price:,.2f}",
                "formatted_change": f"{'+' if change_amount >= 0 else ''}${change_amount:,.2f} ({'+' if percent_change >= 0 else ''}{percent_change:.2f}%)"
            }
            
            # Cache successfully fetched quote
            QUOTE_CACHE[ticker] = (now, quote_result)
            return quote_result
    except Exception as e:
        logger.error(f"Failed to fetch stock quote for {company_name} ({ticker}): {e}")
        return {
            "company_name": company_name,
            "ticker": ticker,
            "is_public": True,
            "error": f"Failed to fetch market quote: {e}"
        }

