from app.nlp.model import get_nlp
from app.nlp.text_processing import normalize_company_name, clean_entity_name
from app.nlp.classification import classify_topic, analyze_sentiment

def extract_entities(text: str) -> dict:
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
