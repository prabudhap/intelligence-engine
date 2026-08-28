def get_organizations(repo) -> list:
    """Retrieves list of workspace organization names."""
    def _tx(tx):
        result = tx.run("""
            MATCH (o:Organization)
            RETURN o.name AS name
            ORDER BY o.name ASC
        """)
        return [record.get("name") for record in result if record.get("name")]

    with repo.get_session() as session:
        return session.execute_read(_tx)

def get_stats(repo, org_name: str) -> dict:
    """Retrieves high-level count metrics for articles, people, and companies in a workspace."""
    def _tx(tx):
        result = tx.run("""
            MATCH (o:Organization {name: $org_name})
            OPTIONAL MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
            WITH o, count(distinct a) as articles
            OPTIONAL MATCH (p:Person)-[:MENTIONED_IN]->(a:Article)-[:UNDER_WORKSPACE]->(o)
            WITH o, articles, count(distinct p) as people
            OPTIONAL MATCH (c:Company)-[:MENTIONED_IN]->(a:Article)-[:UNDER_WORKSPACE]->(o)
            RETURN articles, people, count(distinct c) as companies
        """, org_name=org_name)
        record = result.single()
        if record:
            return {
                "articles": record.get("articles") or 0,
                "people": record.get("people") or 0,
                "companies": record.get("companies") or 0
            }
        return {"articles": 0, "people": 0, "companies": 0}

    with repo.get_session() as session:
        return session.execute_read(_tx)

def _parse_article_records(result) -> list:
    """Formats Neo4j article query records into a standardized dictionary representation."""
    return [
        {
            "title": record.get("title"),
            "created_at": record.get("created_at") or 0,
            "category": record.get("category") or "General",
            "sentiment": record.get("sentiment") or "Neutral",
            "url": record.get("url")
        }
        for record in result
    ]

def get_recent_articles(repo, org_name: str) -> list:
    """Retrieves 20 most recent ingested articles for a workspace."""
    def _tx(tx):
        result = tx.run("""
            MATCH (a:Article)-[:UNDER_WORKSPACE]->(o:Organization {name: $org_name})
            RETURN a.title AS title, a.created_at AS created_at, a.category AS category, a.sentiment AS sentiment, a.url AS url
            ORDER BY a.created_at DESC LIMIT 20
        """, org_name=org_name)
        return _parse_article_records(result)

    with repo.get_session() as session:
        return session.execute_read(_tx)

def get_company_related_articles(repo, company_name: str, org_name: str = "Default") -> list:
    """Retrieves articles related to a specific company/organization node in a workspace."""
    def _tx(tx):
        result = tx.run("""
            MATCH (o:Organization {name: $org_name})
            MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
            MATCH (c)-[:MENTIONED_IN]->(a)
            WHERE (c:Company OR c:Organization OR c:Person) AND (c.name = $company_name OR c.title = $company_name)
            RETURN a.title AS title, a.created_at AS created_at, a.category AS category, a.sentiment AS sentiment, a.url AS url
            ORDER BY a.created_at DESC LIMIT 10
        """, org_name=org_name, company_name=company_name)
        return _parse_article_records(result)

    with repo.get_session() as session:
        return session.execute_read(_tx)

