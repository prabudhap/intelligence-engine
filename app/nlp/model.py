import threading
import spacy
from app.core import logger

_nlp = None
_nlp_lock = threading.Lock()

def get_nlp():
    global _nlp
    if _nlp is None:
        with _nlp_lock:
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
