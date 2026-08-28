import xml.etree.ElementTree as ET

def parse_rss_items(xml_content: bytes, limit: int = 20) -> list[dict]:
    """
    Parses RSS feed XML content and extracts structured article items (title, link, pub_date).
    """
    root = ET.fromstring(xml_content)
    articles = []
    
    for item in root.findall(".//item")[:limit]:
        title_el = item.find("title")
        title = title_el.text if title_el is not None else "Untitled"
        
        link_el = item.find("link")
        link = link_el.text if link_el is not None else ""
        
        pub_date_el = item.find("pubDate")
        pub_date = pub_date_el.text if pub_date_el is not None else None
        
        if title and link:
            articles.append({
                "title": title,
                "link": link,
                "pub_date": pub_date
            })
            
    return articles
