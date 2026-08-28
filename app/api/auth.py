from fastapi import Header, HTTPException
from app.core.config import API_SECRET_KEY

def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")):
    """
    Validates API key header for protected POST/admin operations when API_SECRET_KEY is set.
    If API_SECRET_KEY environment variable is configured, requests lacking valid X-API-Key are rejected.
    """
    if API_SECRET_KEY:
        if not x_api_key or x_api_key != API_SECRET_KEY:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Missing or invalid X-API-Key authentication header."
            )
