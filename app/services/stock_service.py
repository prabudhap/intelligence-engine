import json
import re
from pathlib import Path
import httpx
from app.core import logger

def load_ticker_map(file_path: str | Path | None = None) -> dict[str, str]:
    """Loads ticker symbol mapping dictionary from a JSON resource file."""
    path = Path(file_path) if file_path else Path(__file__).parent.parent / "resources" / "ticker_map.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

TICKER_MAP = load_ticker_map()

def resolve_ticker_symbol(company_name: str) -> str | None:
    """Resolves a company name string to a stock ticker symbol."""
    if not company_name:
        return None
        
    clean = company_name.upper().strip()
    # Strip common corporate suffixes for matching
    clean_base = re.sub(r'\b(INC|LLC|LTD|CORP|CORPORATION|LIMITED|CO|COMPANY)\b\.?$', '', clean).strip()
    clean_base = re.sub(r'[\s,\.]+$', '', clean_base).strip()
    
    if clean in TICKER_MAP:
        return TICKER_MAP[clean]
    if clean_base in TICKER_MAP:
        return TICKER_MAP[clean_base]
        
    # Partial substring search
    for name_key, ticker in TICKER_MAP.items():
        if name_key in clean_base or clean_base in name_key:
            return ticker
            
    # If the input looks like a raw 2-5 letter ticker symbol
    if re.match(r'^[A-Z]{2,5}$', clean_base):
        return clean_base
        
    return None

def fetch_stock_quote(company_name: str) -> dict:
    """
    Fetches real-time USD stock price, previous close, and price change 
    from Yahoo Finance API for a company.
    """
    ticker = resolve_ticker_symbol(company_name)
    if not ticker:
        return {
            "company_name": company_name,
            "ticker": None,
            "is_public": False,
            "message": "Private / Unlisted Entity"
        }
        
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
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
            
            return {
                "company_name": company_name,
                "ticker": ticker,
                "is_public": True,
                "currency": "USD",
                "current_price": round(current_price, 2),
                "previous_close": round(previous_close, 2),
                "change_amount": round(change_amount, 2),
                "percent_change": round(percent_change, 2),
                "is_up": change_amount >= 0,
                "formatted_price": f"${current_price:,.2f}",
                "formatted_change": f"{'+' if change_amount >= 0 else ''}${change_amount:,.2f} ({'+' if percent_change >= 0 else ''}{percent_change:.2f}%)"
            }
    except Exception as e:
        logger.error(f"Failed to fetch stock quote for {company_name} ({ticker}): {e}")
        return {
            "company_name": company_name,
            "ticker": ticker,
            "is_public": True,
            "error": f"Failed to fetch market quote: {e}"
        }
