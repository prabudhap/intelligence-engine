import logging
import re
import spacy

logger = logging.getLogger("uvicorn.error")
_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("spaCy model 'en_core_web_sm' not found. Attempting to download...")
            from spacy.cli import download
            try:
                download("en_core_web_sm")
                _nlp = spacy.load("en_core_web_sm")
                logger.info("Successfully downloaded and loaded spaCy model 'en_core_web_sm'.")
            except Exception as e:
                logger.error(f"Failed to download spaCy model 'en_core_web_sm': {e}")
                raise e
    return _nlp

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

def extract_entities(text: str):
    """
    Analyzes document text to extract people, companies, and locations,
    mapping relationships based on paragraph proximity.
    """
    nlp = get_nlp()
    
    # Extract unique raw entities across the entire document
    doc_full = nlp(text)
    
    raw_companies = list(set([ent.text for ent in doc_full.ents if ent.label_ == "ORG"]))
    raw_people = list(set([ent.text for ent in doc_full.ents if ent.label_ == "PERSON"]))
    raw_locations = list(set([ent.text for ent in doc_full.ents if ent.label_ == "GPE"]))
    
    # Clean and normalize names
    companies = list(set([normalize_company_name(name) for name in raw_companies]))
    people = list(set([clean_entity_name(name) for name in raw_people]))
    locations = list(set([clean_entity_name(name) for name in raw_locations]))
    
    # Filter empty or trivial results
    companies = [c for c in companies if len(c) > 1]
    people = [p for p in people if len(p) > 1]
    locations = [l for l in locations if len(l) > 1]
    
    # Track relationships using paragraph-level proximity (paragraphs separated by \n\n)
    relationships = set()
    location_relationships = set()
    
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for paragraph in paragraphs:
        p_doc = nlp(paragraph)
        p_companies = set([normalize_company_name(ent.text) for ent in p_doc.ents if ent.label_ == "ORG"])
        p_people = set([clean_entity_name(ent.text) for ent in p_doc.ents if ent.label_ == "PERSON"])
        p_locations = set([clean_entity_name(ent.text) for ent in p_doc.ents if ent.label_ == "GPE"])
        
        # Filter matching elements
        p_companies = {c for c in p_companies if len(c) > 1}
        p_people = {p for p in p_people if len(p) > 1}
        p_locations = {l for l in p_locations if len(l) > 1}
        
        # Cross-reference people and companies in this paragraph
        for p in p_people:
            for c in p_companies:
                relationships.add((p, c))
                
        # Cross-reference people and locations in this paragraph
        for p in p_people:
            for l in p_locations:
                location_relationships.add((p, l))
                
    # Re-structure as expected schema representations
    relationships_list = [{"person": r[0], "company": r[1]} for r in relationships]
    loc_relationships_list = [{"person": r[0], "location": r[1]} for r in location_relationships]
    
    return {
        "companies": companies,
        "people": people,
        "locations": locations,
        "relationships": relationships_list,
        "location_relationships": loc_relationships_list
    }