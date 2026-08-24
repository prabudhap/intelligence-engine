import re

def normalize_company_name(name: str) -> str:
    """
    Cleans company names by removing trailing spaces, punctuation,
    collapsing multiple internal spaces, and common corporate suffixes (Inc., LLC, Ltd., Corp., etc.).
    """
    if not name:
        return ""
    name = re.sub(r'\s+', ' ', name.strip())
    # Regex to match common suffixes case-insensitively at the end of the word
    pattern = r'\b(inc(orporated)?|l\.?l\.?c\.?|corp(oration)?|ltd|limited|co(mpany)?)\b\.?$'
    normalized = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()
    # Strip any trailing comma or dot that prefixed the suffix
    normalized = re.sub(r'[\s,\.]+$', '', normalized).strip()
    return re.sub(r'\s+', ' ', normalized) if normalized else name

def clean_entity_name(name: str) -> str:
    """
    Clean basic whitespace, internal duplicate spaces, and punctuation for entity names.
    """
    if not name:
        return ""
    cleaned = re.sub(r'\s+', ' ', name.strip().strip(",.- "))
    return cleaned.title()
