import re

CATEGORIES = {
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

CATEGORY_PATTERNS = {
    cat: [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in keywords]
    for cat, keywords in CATEGORIES.items()
}

def classify_topic(text: str) -> str:
    """
    Classifies the text into a major category using pre-compiled regex keyword patterns.
    """
    scores = {}
    for cat, patterns in CATEGORY_PATTERNS.items():
        score = sum(len(p.findall(text)) for p in patterns)
        scores[cat] = score
        
    best_category = "General"
    max_score = 0
    for cat, score in scores.items():
        if score > max_score:
            max_score = score
            best_category = cat
            
    return best_category

WORD_TOKEN_RE = re.compile(r'\b[a-z]+\b')

def analyze_sentiment(text: str) -> str:
    """
    Performs a lightweight lexicon-based sentiment analysis on the text.
    Uses pre-compiled regex tokenizer for high-speed evaluation.
    """
    text_lower = text.lower()
    
    positive_words = {
        'good', 'great', 'positive', 'win', 'success', 'benefit', 'growth', 'gain', 
        'advance', 'improve', 'improved', 'improving', 'strengthen', 'strengthened', 
        'innovative', 'profit', 'profitable', 'optimistic', 'boost', 'upgrade', 
        'breakthrough', 'leadership', 'expand', 'expanded', 'partnership', 'alliance', 
        'solve', 'solution', 'happy', 'pleased', 'excellent', 'achieve', 'achievement',
        'surpass', 'beat', 'reward', 'advantage', 'dividend', 'outperform', 'rebound', 
        'soared', 'soar', 'thrive'
    }
    
    negative_words = {
        'bad', 'poor', 'negative', 'loss', 'fail', 'failure', 'failed', 'decline', 
        'declined', 'declining', 'drop', 'dropped', 'risk', 'risky', 'threat', 'threaten', 
        'warn', 'warning', 'weak', 'weakness', 'decrease', 'decreased', 'lawsuit', 'sue', 
        'sued', 'suing', 'investigate', 'investigation', 'fine', 'fined', 'crisis', 
        'layoff', 'laid off', 'cut', 'delay', 'delayed', 'conflict', 'sanction', 
        'breach', 'vulnerability', 'deficit', 'disaster', 'prosecute', 'charge', 'accuse',
        'damage', 'hurt', 'harm', 'bankruptcy', 'insolvency', 'default', 'surrender', 
        'collapse', 'catastrophic'
    }
    
    words = WORD_TOKEN_RE.findall(text_lower)
    
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
