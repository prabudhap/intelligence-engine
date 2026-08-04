import os
import re
import time
from typing import cast, LiteralString
from neo4j import GraphDatabase


class Database:
    def __init__(self):
        # Read parameters passed from docker-compose orchestration
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "secure_password_123")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def setup_constraints(self):
        constraints = [
            ("org_name_unique", "Organization", "name"),
            ("article_title_unique", "Article", "title"),
            ("person_name_unique", "Person", "name"),
            ("company_name_unique", "Company", "name"),
            ("location_name_unique", "Location", "name"),
        ]
        with self.driver.session() as session:
            for c_name, label, prop in constraints:
                try:
                    # Execute write transaction for constraints setup (Neo4j 5 syntax)
                    session.run(cast(LiteralString, f"CREATE CONSTRAINT {c_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"))
                except Exception as e:
                    import logging
                    logger = logging.getLogger("uvicorn.error")
                    logger.warning(f"Failed to create constraint {c_name} using Neo4j 5 syntax: {e}. Retrying with legacy syntax...")
                    try:
                        # Legacy Neo4j 4.x syntax fallback
                        session.run(cast(LiteralString, f"CREATE CONSTRAINT {c_name} IF NOT EXISTS ON (n:{label}) ASSERT n.{prop} IS UNIQUE"))
                    except Exception as e2:
                        logger.error(f"Fallback constraint creation failed: {e2}")

    def save_intelligence(self, org_name: str, title: str, entities: dict, body: str = ""):
        with self.driver.session() as session:
            session.execute_write(self._cypher_transaction, org_name, title, entities, body)

    @staticmethod
    def _cypher_transaction(tx, org_name, title, entities, body):
        # 1. Merge the Organization workspace node
        tx.run("MERGE (o:Organization {name: $org_name})", org_name=org_name)

        # 2. Merge the Article node with a timestamp and body
        current_time = int(time.time() * 1000)
        tx.run("""
            MERGE (a:Article {title: $title})
            ON CREATE SET a.created_at = $created_at, a.body = $body
            ON MATCH SET a.body = $body
        """, title=title, created_at=current_time, body=body)
        
        # 3. Link the Article to the Organization
        tx.run("""
            MATCH (o:Organization {name: $org_name})
            MATCH (a:Article {title: $title})
            MERGE (a)-[:UNDER_WORKSPACE]->(o)
        """, org_name=org_name, title=title)
        
        # 4. Batch merge Companies and link them to the Article
        companies = entities.get("companies", [])
        if companies:
            tx.run("""
                MATCH (a:Article {title: $title})
                UNWIND $companies AS company_name
                MERGE (c:Company {name: company_name})
                MERGE (c)-[:MENTIONED_IN]->(a)
            """, title=title, companies=companies)
            
        # 5. Batch merge People and link them to the Article
        people = entities.get("people", [])
        if people:
            tx.run("""
                MATCH (a:Article {title: $title})
                UNWIND $people AS person_name
                MERGE (p:Person {name: person_name})
                MERGE (p)-[:MENTIONED_IN]->(a)
            """, title=title, people=people)

        # 6. Batch merge Locations and link them to the Article
        locations = entities.get("locations", [])
        if locations:
            tx.run("""
                MATCH (a:Article {title: $title})
                UNWIND $locations AS loc_name
                MERGE (l:Location {name: loc_name})
                MERGE (l)-[:MENTIONED_IN]->(a)
            """, title=title, locations=locations)
            
        # 7. Batch merge relationships between People and Companies
        relationships = entities.get("relationships", [])
        if relationships:
            tx.run("""
                UNWIND $relationships AS rel
                MATCH (p:Person {name: rel.person})
                MATCH (c:Company {name: rel.company})
                MERGE (p)-[:INDIRECTLY_INVOLVED_WITH]->(c)
            """, relationships=relationships)

        # 8. Batch merge relationships between People and Locations
        location_relationships = entities.get("location_relationships", [])
        if location_relationships:
            tx.run("""
                UNWIND $location_relationships AS rel
                MATCH (p:Person {name: rel.person})
                MATCH (l:Location {name: rel.location})
                MERGE (p)-[:LOCATED_IN]->(l)
            """, location_relationships=location_relationships)

    def get_organizations(self) -> list:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (o:Organization)
                RETURN o.name AS name
                ORDER BY o.name ASC
            """)
            return [record.get("name") for record in result if record.get("name")]

    def get_stats(self, org_name: str) -> dict:
        with self.driver.session() as session:
            result = session.run("""
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

    def get_recent_articles(self, org_name: str) -> list:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o:Organization {name: $org_name})
                RETURN a.title AS title, a.created_at AS created_at
                ORDER BY a.created_at DESC LIMIT 20
            """, org_name=org_name)
            articles = []
            for record in result:
                articles.append({
                    "title": record.get("title"),
                    "created_at": record.get("created_at") or 0
                })
            return articles

    def get_graph_data(self, org_name: str) -> dict:
        nodes = []
        edges = []
        seen_nodes = set()
        seen_edges = set()

        def add_node(node, group_name):
            if not node:
                return
            node_id = node.element_id
            if node_id not in seen_nodes:
                title = node.get("title") or node.get("name") or "Unnamed"
                nodes.append({
                    "id": node_id,
                    "label": title,
                    "group": group_name
                })
                seen_nodes.add(node_id)

        def add_edge(start_node, end_node, rel_type):
            if not start_node or not end_node or not rel_type:
                return
            edge_key = (start_node.element_id, end_node.element_id, rel_type)
            if edge_key not in seen_edges:
                edges.append({
                    "from": start_node.element_id,
                    "to": end_node.element_id,
                    "label": rel_type
                })
                seen_edges.add(edge_key)

        with self.driver.session() as session:
            # 1. Fetch organization and articles
            res_articles = session.run("""
                MATCH (o:Organization {name: $org_name})
                OPTIONAL MATCH (a:Article)-[r_uw:UNDER_WORKSPACE]->(o)
                RETURN o, a, r_uw
            """, org_name=org_name)
            
            for record in res_articles:
                o = record.get("o")
                a = record.get("a")
                add_node(o, "Organization")
                if a:
                    add_node(a, "Article")
                    add_edge(a, o, "UNDER_WORKSPACE")

            # 2. Fetch all entities mentioned in articles under this workspace
            res_entities = session.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                MATCH (ent)-[r_m:MENTIONED_IN]->(a)
                RETURN ent, a, r_m
            """, org_name=org_name)
            
            for record in res_entities:
                ent = record.get("ent")
                a = record.get("a")
                if ent:
                    label = list(ent.labels)[0] if ent.labels else "Unknown"
                    add_node(ent, label)
                    add_edge(ent, a, "MENTIONED_IN")

            # 3. Fetch relationships between these entities
            res_rels = session.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                MATCH (p:Person)-[:MENTIONED_IN]->(a)
                MATCH (c:Company)-[:MENTIONED_IN]->(a)
                MATCH (p)-[r:INDIRECTLY_INVOLVED_WITH]->(c)
                RETURN p, c, r
            """, org_name=org_name)
            for record in res_rels:
                p = record.get("p")
                c = record.get("c")
                add_node(p, "Person")
                add_node(c, "Company")
                add_edge(p, c, "INDIRECTLY_INVOLVED_WITH")

            res_rels_loc = session.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                MATCH (p:Person)-[:MENTIONED_IN]->(a)
                MATCH (l:Location)-[:MENTIONED_IN]->(a)
                MATCH (p)-[r:LOCATED_IN]->(l)
                RETURN p, l, r
            """, org_name=org_name)
            for record in res_rels_loc:
                p = record.get("p")
                l = record.get("l")
                add_node(p, "Person")
                add_node(l, "Location")
                add_edge(p, l, "LOCATED_IN")

        return {"nodes": nodes, "edges": edges}

    def get_shortest_path(self, source_name: str, target_name: str) -> dict:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source) WHERE source.name = $source_name OR source.title = $source_name
                MATCH (target) WHERE target.name = $target_name OR target.title = $target_name
                MATCH p = shortestPath((source)-[*..6]-(target))
                RETURN p
            """, source_name=source_name, target_name=target_name)
            
            record = result.single()
            if not record or not record.get("p"):
                return {"nodes": [], "edges": []}
                
            path = record.get("p")
            nodes = []
            edges = []
            seen_nodes = set()
            seen_edges = set()
            
            for node in path.nodes:
                if node.element_id not in seen_nodes:
                    label = list(node.labels)[0] if node.labels else "Unknown"
                    title = node.get("title") or node.get("name") or "Unnamed"
                    nodes.append({
                        "id": node.element_id,
                        "label": title,
                        "group": label
                    })
                    seen_nodes.add(node.element_id)
                
            for rel in path.relationships:
                edge_key = (rel.start_node.element_id, rel.end_node.element_id, rel.type)
                if edge_key not in seen_edges:
                    context_data = self.get_relationship_context(
                        session, rel.type, rel.start_node.element_id, rel.end_node.element_id
                    )
                    edges.append({
                        "from": rel.start_node.element_id,
                        "to": rel.end_node.element_id,
                        "label": rel.type,
                        "context": context_data.get("context", ""),
                        "full_context": context_data.get("full_context", "")
                    })
                    seen_edges.add(edge_key)
                
            return {"nodes": nodes, "edges": edges}

    def get_relationship_context(self, session, rel_type: str, start_id: str, end_id: str) -> dict:
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
        body = record.get("body")
        
        # Split body into paragraphs
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
            
        # Split paragraph into sentences using regular expression terminal punctuation matching
        sentences = re.split(r'(?<=[.!?])\s+', matched_paragraph)
        relevant_sentences = []
        
        # Keep sentences containing both names
        for s in sentences:
            if name1.lower() in s.lower() and name2.lower() in s.lower():
                relevant_sentences.append(s)
                
        # If none, keep sentences containing at least one of the names
        if not relevant_sentences:
            for s in sentences:
                if name1.lower() in s.lower() or name2.lower() in s.lower():
                    relevant_sentences.append(s)
                    
        # Fallback to the first sentence if none match specifically
        if not relevant_sentences and sentences:
            relevant_sentences.append(sentences[0])
            
        summary = " ".join(relevant_sentences).strip()
        
        # Cap length at 280 characters to keep it compact and readable in tooltips
        if len(summary) > 280:
            summary = summary[:277] + "..."
            
        return {"context": summary, "full_context": matched_paragraph}