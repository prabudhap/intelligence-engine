import re

MULTIPLE_SPACES_RE = re.compile(r'\s+')
CORPORATE_SUFFIX_RE = re.compile(r'\b(inc(orporated)?|l\.?l\.?c\.?|corp(oration)?|ltd|limited|co(mpany)?)\b\.?$', re.IGNORECASE)
TRAILING_PUNCT_RE = re.compile(r'[\s,\.]+$')

def normalize_company_name(name: str) -> str:
    """
    Cleans company names by removing trailing spaces, punctuation,
    collapsing multiple internal spaces, and common corporate suffixes (Inc., LLC, Ltd., Corp., etc.).
    Uses pre-compiled regexes for maximum throughput.
    """
    if not name:
        return ""
    clean = MULTIPLE_SPACES_RE.sub(' ', name.strip())
    normalized = CORPORATE_SUFFIX_RE.sub('', clean).strip()
    normalized = TRAILING_PUNCT_RE.sub('', normalized).strip()
    return MULTIPLE_SPACES_RE.sub(' ', normalized) if normalized else clean

def clean_entity_name(name: str) -> str:
    """
    Clean basic whitespace, internal duplicate spaces, and punctuation for entity names.
    """
    if not name:
        return ""
    cleaned = MULTIPLE_SPACES_RE.sub(' ', name.strip().strip(",.- "))
    return cleaned.title()
