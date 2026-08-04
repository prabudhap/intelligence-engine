import os
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

    def save_intelligence(self, org_name: str, title: str, entities: dict):
        with self.driver.session() as session:
            session.execute_write(self._cypher_transaction, org_name, title, entities)

    @staticmethod
    def _cypher_transaction(tx, org_name, title, entities):
        # 1. Merge the Organization workspace node
        tx.run("MERGE (o:Organization {name: $org_name})", org_name=org_name)

        # 2. Merge the Article node with a timestamp
        current_time = int(time.time() * 1000)
        tx.run("""
            MERGE (a:Article {title: $title})
            ON CREATE SET a.created_at = $created_at
        """, title=title, created_at=current_time)
        
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
            result = session.run("""
                MATCH (o:Organization {name: $org_name})
                OPTIONAL MATCH (a:Article)-[r_uw:UNDER_WORKSPACE]->(o)
                OPTIONAL MATCH (ent)-[r_m:MENTIONED_IN]->(a)
                OPTIONAL MATCH (p:Person)-[r_iiw:INDIRECTLY_INVOLVED_WITH]->(c:Company)
                WHERE (p)-[:MENTIONED_IN]->(a) AND (c)-[:MENTIONED_IN]->(a)
                OPTIONAL MATCH (p)-[r_li:LOCATED_IN]->(l:Location)
                WHERE (p)-[:MENTIONED_IN]->(a) AND (l)-[:MENTIONED_IN]->(a)
                RETURN o, a, ent, p, c, l, r_uw, r_m, r_iiw, r_li
            """, org_name=org_name)

            for record in result:
                o = record.get("o")
                a = record.get("a")
                ent = record.get("ent")
                p = record.get("p")
                c = record.get("c")
                l = record.get("l")

                # Add nodes
                add_node(o, "Organization")
                add_node(a, "Article")
                if ent:
                    label = list(ent.labels)[0] if ent.labels else "Unknown"
                    add_node(ent, label)
                add_node(p, "Person")
                add_node(c, "Company")
                add_node(l, "Location")

                # Add relationships
                if a and o:
                    add_edge(a, o, "UNDER_WORKSPACE")
                if ent and a:
                    add_edge(ent, a, "MENTIONED_IN")
                if p and c:
                    add_edge(p, c, "INDIRECTLY_INVOLVED_WITH")
                if p and l:
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
                    edges.append({
                        "from": rel.start_node.element_id,
                        "to": rel.end_node.element_id,
                        "label": rel.type
                    })
                    seen_edges.add(edge_key)
                
            return {"nodes": nodes, "edges": edges}