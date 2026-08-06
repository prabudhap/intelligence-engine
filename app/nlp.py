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

def classify_topic(text: str) -> str:
    """
    Classifies the text into a major category based on case-insensitive keyword occurrences.
    """
    text_lower = text.lower()
    
    categories = {
        "Technology": [
            'ai', 'artificial intelligence', 'software', 'technology', 'semiconductor', 
            'chip', 'cloud', 'data', 'robot', 'cyber', 'quantum', 'computer', 'developer',
            'algorithm', 'app', 'hardware', 'gpu', 'cpu', 'system'
        ],
        "Finance": [
            'finance', 'inflation', 'stock', 'investment', 'economy', 'acquisition', 
            'merger', 'market', 'trade', 'tax', 'bank', 'earnings', 'revenue', 'funding',
            'deal', 'valuation', 'capital', 'crypto', 'bitcoin', 'shareholder', 'dollar'
        ],
        "Geopolitics": [
            'geopolitics', 'summit', 'diplomatic', 'government', 'treaty', 'sanction', 
            'election', 'minister', 'president', 'border', 'policy', 'relations', 'un',
            'ambassador', 'administration', 'legislation', 'senate', 'parliament'
        ],
        "Defense": [
            'defense', 'military', 'conflict', 'security', 'war', 'cybersecurity', 
            'intelligence', 'threat', 'pentagon', 'weapon', 'strike', 'navy', 'army', 
            'air force', 'attack', 'hacker', 'exploit', 'malware', 'combat'
        ],
        "Healthcare": [
            'healthcare', 'medical', 'science', 'health', 'disease', 'vaccine', 'fda', 
            'biotech', 'clinical', 'pharma', 'energy', 'climate', 'carbon', 'emission',
            'patient', 'hospital', 'drug', 'treatment', 'medicine', 'biology'
        ]
    }
    
    scores = {}
    for cat, keywords in categories.items():
        score = 0
        for keyword in keywords:
            score += len(re.findall(r'\b' + re.escape(keyword) + r'\b', text_lower))
        scores[cat] = score
        
    best_category = "General"
    max_score = 0
    for cat, score in scores.items():
        if score > max_score:
            max_score = score
            best_category = cat
            
    return best_category

def analyze_sentiment(text: str) -> str:
    """
    Performs a lightweight lexicon-based sentiment analysis on the text.
    """
    text_lower = text.lower()
    
    positive_words = {
        'good', 'great', 'positive', 'win', 'success', 'benefit', 'growth', 'gain', 
        'advance', 'improve', 'improved', 'improving', 'strengthen', 'strengthened', 
        'innovative', 'profit', 'profitable', 'optimistic', 'boost', 'upgrade', 
        'breakthrough', 'leadership', 'expand', 'expanded', 'partnership', 'alliance', 
        'solve', 'solution', 'happy', 'pleased', 'excellent', 'achieve', 'achievement',
        'surpass', 'beat', 'reward', 'advantage'
    }
    
    negative_words = {
        'bad', 'poor', 'negative', 'loss', 'fail', 'failure', 'failed', 'decline', 
        'declined', 'declining', 'drop', 'dropped', 'risk', 'risky', 'threat', 'threaten', 
        'warn', 'warning', 'weak', 'weakness', 'decrease', 'decreased', 'lawsuit', 'sue', 
        'sued', 'suing', 'investigate', 'investigation', 'fine', 'fined', 'crisis', 
        'layoff', 'laid off', 'cut', 'delay', 'delayed', 'conflict', 'sanction', 
        'breach', 'vulnerability', 'deficit', 'disaster', 'prosecute', 'charge', 'accuse',
        'damage', 'hurt', 'harm'
    }
    
    words = re.findall(r'\b[a-z]+\b', text_lower)
    
    pos_count = sum(1 for w in words if w in positive_words)
    neg_count = sum(1 for w in words if w in negative_words)
    
    total = pos_count + neg_count
    if total == 0:
        return "Neutral"
        
    polarity = (pos_count - neg_count) / total
    
    if polarity >= 0.15:
        return "Positive"
    elif polarity <= -0.15:
        return "Negative"
    else:
        return "Neutral"

def extract_entities(text: str):
    """
    Analyzes document text to extract people, companies, and locations,
    mapping relationships based on paragraph proximity, and classifies topic & sentiment.
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
    
    # Classify topic and analyze sentiment
    category = classify_topic(text)
    sentiment = analyze_sentiment(text)
    
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
        "location_relationships": loc_relationships_list,
        "category": category,
        "sentiment": sentiment
    }