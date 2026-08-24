import email.utils
import re
from datetime import datetime

def get_temporal_info(pub_date_str: str | None = None) -> dict:
    dt = None
    if pub_date_str:
        try:
            parsed_date = email.utils.parsedate_to_datetime(pub_date_str)
            if parsed_date:
                dt = parsed_date
        except Exception:
            pass
    if not dt:
        dt = datetime.now()
        
    year = dt.year
    month = dt.month
    month_name = dt.strftime("%B")
    iso_year, week_num, day_of_week = dt.isocalendar()
    day = dt.day
    
    hour = dt.hour
    if 0 <= hour < 6:
        period_val = "00:00-06:00"
        period_id_suffix = "00"
    elif 6 <= hour < 12:
        period_val = "06:00-12:00"
        period_id_suffix = "06"
    elif 12 <= hour < 18:
        period_val = "12:00-18:00"
        period_id_suffix = "12"
    else:
        period_val = "18:00-24:00"
        period_id_suffix = "18"
        
    year_id = str(year)
    month_id = f"{year}-{month:02d}"
    week_id = f"{year}-W{week_num:02d}"
    day_id = f"{year}-{month:02d}-{day:02d}"
    period_id = f"{day_id}-{period_id_suffix}"
    
    return {
        "year": year,
        "year_id": year_id,
        "month": month,
        "month_name": month_name,
        "month_id": month_id,
        "week": week_num,
        "week_id": week_id,
        "day": day,
        "day_id": day_id,
        "period": period_val,
        "period_id": period_id,
        "timestamp": int(dt.timestamp() * 1000)
    }

def extract_context_from_text(body: str, name1: str, name2: str) -> dict:
    """
    Extracts sentence-level and paragraph-level context for two entities from article body text in memory.
    """
    if not body or not (name1 or name2):
        return {"context": "", "full_context": ""}
        
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    
    # 1. Search for paragraph containing both names
    matched_paragraph = ""
    for p in paragraphs:
        if name1.lower() in p.lower() and name2.lower() in p.lower():
            matched_paragraph = p
            break
            
    # 2. Fallback: Search for paragraph containing at least one of them
    if not matched_paragraph:
        for p in paragraphs:
            if name1.lower() in p.lower() or name2.lower() in p.lower():
                matched_paragraph = p
                break
                
    if not matched_paragraph:
        return {"context": "", "full_context": ""}
        
    sentences = re.split(r'(?<=[.!?])\s+', matched_paragraph)
    relevant_sentences = []
    
    for s in sentences:
        if name1.lower() in s.lower() and name2.lower() in s.lower():
            relevant_sentences.append(s)
            
    if not relevant_sentences:
        for s in sentences:
            if name1.lower() in s.lower() or name2.lower() in s.lower():
                relevant_sentences.append(s)
                
    if not relevant_sentences and sentences:
        relevant_sentences.append(sentences[0])
        
    summary = " ".join(relevant_sentences).strip()
    if len(summary) > 280:
        summary = summary[:277] + "..."
        
    return {"context": summary, "full_context": matched_paragraph}

def extract_context_from_bodies(bodies: list[str], name1: str, name2: str) -> dict:
    """
    Searches a list of in-memory article bodies for matching entity relationship context.
    """
    best_context = {"context": "", "full_context": ""}
    for body in bodies:
        ctx = extract_context_from_text(body, name1, name2)
        if ctx["context"]:
            return ctx
        if not best_context["full_context"] and ctx["full_context"]:
            best_context = ctx
    return best_context

def get_relationship_context(session, rel_type: str, start_id: str, end_id: str) -> dict:
    """
    Legacy database-backed relationship context extractor fallback.
    """
    query = """
        MATCH (n1) WHERE elementId(n1) = $start_id
        MATCH (n2) WHERE elementId(n2) = $end_id
        WITH n1, n2
        OPTIONAL MATCH (a:Article) 
        WHERE a.body IS NOT NULL AND (
            (elementId(a) = $start_id) OR (elementId(a) = $end_id) OR
            ((n1)-[:MENTIONED_IN]->(a) AND (n2)-[:MENTIONED_IN]->(a))
        )
        RETURN n1.name as name1, n1.title as title1, 
               n2.name as name2, n2.title as title2, 
               a.body as body
        LIMIT 1
    """
    result = session.run(query, start_id=start_id, end_id=end_id)
    record = result.single()
    if not record or not record.get("body"):
        return {"context": "", "full_context": ""}
        
    name1 = record.get("name1") or record.get("title1") or ""
    name2 = record.get("name2") or record.get("title2") or ""
    return extract_context_from_text(record.get("body"), name1, name2)

