import logging
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

def extract_entities(text: str):
    nlp = get_nlp()
    doc = nlp(text)
    companies = list(set([ent.text for ent in doc.ents if ent.label_ == "ORG"]))
    people = list(set([ent.text for ent in doc.ents if ent.label_ == "PERSON"]))
    
    relationships = []
    if people and companies:
        for p in people:
            for c in companies:
                relationships.append({"person": p, "company": c})
                
    return {
        "companies": companies,
        "people": people,
        "relationships": relationships
    }