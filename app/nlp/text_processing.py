import re

def normalize_company_name(name: str) -> str:
    """
    Cleans company names by removing trailing spaces, punctuation,
    and common corporate suffixes (Inc., LLC, Ltd., Corp., etc.).
    """
    name = name.strip()
    # Regex to match common suffixes case-insensitively at the end of the word
    pattern = r'\b(inc(orporated)?|l\.?l\.?c\.?|corp(oration)?|ltd|limited|co(mpany)?)\b\.?$'
    normalized = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()
    # Strip any trailing comma or dot that prefixed the suffix
    normalized = re.sub(r'[\s,\.]+$', '', normalized).strip()
    return normalized if normalized else name

def clean_entity_name(name: str) -> str:
    """
    Clean basic whitespace and punctuation prefixes/suffixes for names and locations.
    """
    return name.strip().strip(",.- ").title()
