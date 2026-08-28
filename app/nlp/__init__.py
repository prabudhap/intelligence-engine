from app.nlp.model import get_nlp
from app.nlp.text_processing import normalize_company_name, clean_entity_name
from app.nlp.classification import classify_topic, analyze_sentiment

def _filter_entity_set(raw_texts, normalizer_fn) -> list[str]:
    """Normalizes and filters entity name strings, omitting empty or single-character names."""
    cleaned = {normalizer_fn(t) for t in raw_texts if t}
    return [name for name in cleaned if len(name) > 1]

def extract_entities(text: str) -> dict:
    """
    Analyzes document text to extract people, companies, and locations,
    mapping relationships based on paragraph proximity, and classifies topic & sentiment.
    """
    nlp = get_nlp()
    
    # Extract unique raw entities across the entire document
    doc_full = nlp(text)
    
    companies = _filter_entity_set(
        [ent.text for ent in doc_full.ents if ent.label_ == "ORG"], normalize_company_name
    )
    people = _filter_entity_set(
        [ent.text for ent in doc_full.ents if ent.label_ == "PERSON"], clean_entity_name
    )
    locations = _filter_entity_set(
        [ent.text for ent in doc_full.ents if ent.label_ == "GPE"], clean_entity_name
    )
    
    # Classify topic and analyze sentiment
    category = classify_topic(text)
    sentiment = analyze_sentiment(text)
    
    # Track relationships using paragraph-level proximity (paragraphs separated by \n\n)
    relationships = set()
    location_relationships = set()
    
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for paragraph in paragraphs:
        p_doc = nlp(paragraph)
        p_companies = set(_filter_entity_set([ent.text for ent in p_doc.ents if ent.label_ == "ORG"], normalize_company_name))
        p_people = set(_filter_entity_set([ent.text for ent in p_doc.ents if ent.label_ == "PERSON"], clean_entity_name))
        p_locations = set(_filter_entity_set([ent.text for ent in p_doc.ents if ent.label_ == "GPE"], clean_entity_name))
        
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
