from typing import Any
from app.database.temporal import get_temporal_info, get_relationship_context

class DatabaseRepository:
    def __init__(self, driver=None):
        self.driver = driver

    def get_session(self):
        if not self.driver:
            raise RuntimeError("Neo4j database driver is not initialized or has been closed.")
        return self.driver.session()

    def save_intelligence(self, org_name: str, title: str, entities: dict, body: str = "", pub_date: str | None = None, url: str | None = None):
        with self.get_session() as session:
            session.execute_write(self._cypher_transaction, org_name, title, entities, body, pub_date, url)

    @staticmethod
    def _cypher_transaction(tx: Any, org_name: str, title: str, entities: dict, body: str, pub_date: str | None = None, url: str | None = None):
        # 1. Merge the Organization workspace node
        tx.run("MERGE (o:Organization {name: $org_name})", org_name=org_name)

        # Resolve temporal info
        temp_info = get_temporal_info(pub_date)

        # Merge the temporal tree hierarchy branch
        tx.run("""
            MERGE (y:Year {id: $year_id})
            ON CREATE SET y.value = $year
            
            MERGE (m:Month {id: $month_id})
            ON CREATE SET m.value = $month, m.name = $month_name
            MERGE (y)-[:HAS_MONTH]->(m)
            
            MERGE (w:Week {id: $week_id})
            ON CREATE SET w.value = $week
            MERGE (m)-[:HAS_WEEK]->(w)
            
            MERGE (d:Day {id: $day_id})
            ON CREATE SET d.value = $day
            MERGE (w)-[:HAS_DAY]->(d)
            
            MERGE (tp:TimePeriod {id: $period_id})
            ON CREATE SET tp.value = $period
            MERGE (d)-[:HAS_PERIOD]->(tp)
        """, 
        year_id=temp_info["year_id"], year=temp_info["year"],
        month_id=temp_info["month_id"], month=temp_info["month"], month_name=temp_info["month_name"],
        week_id=temp_info["week_id"], week=temp_info["week"],
        day_id=temp_info["day_id"], day=temp_info["day"],
        period_id=temp_info["period_id"], period=temp_info["period"])

        # 2. Merge the Article node with a timestamp, body, category, and sentiment
        current_time = temp_info["timestamp"]
        category = entities.get("category", "General")
        sentiment = entities.get("sentiment", "Neutral")
        tx.run("""
            MERGE (a:Article {title: $title})
            ON CREATE SET a.created_at = $created_at, a.body = $body, a.category = $category, a.sentiment = $sentiment, a.url = $url
            ON MATCH SET a.body = $body, a.category = $category, a.sentiment = $sentiment, a.url = $url
        """, title=title, created_at=current_time, body=body, category=category, sentiment=sentiment, url=url)
        
        # Link the Article to the temporal Period
        tx.run("""
            MATCH (tp:TimePeriod {id: $period_id})
            MATCH (a:Article {title: $title})
            MERGE (tp)-[:HAS_ARTICLE]->(a)
        """, period_id=temp_info["period_id"], title=title)

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
        with self.get_session() as session:
            result = session.run("""
                MATCH (o:Organization)
                RETURN o.name AS name
                ORDER BY o.name ASC
            """)
            return [record.get("name") for record in result if record.get("name")]

    def get_stats(self, org_name: str) -> dict:
        with self.get_session() as session:
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
        with self.get_session() as session:
            result = session.run("""
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o:Organization {name: $org_name})
                RETURN a.title AS title, a.created_at AS created_at, a.category AS category, a.sentiment AS sentiment, a.url AS url
                ORDER BY a.created_at DESC LIMIT 20
            """, org_name=org_name)
            articles = []
            for record in result:
                articles.append({
                    "title": record.get("title"),
                    "created_at": record.get("created_at") or 0,
                    "category": record.get("category") or "General",
                    "sentiment": record.get("sentiment") or "Neutral",
                    "url": record.get("url")
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
                title = node.get("title") or node.get("name") or node.get("id") or node.get("value") or "Unnamed"
                if group_name == "Year":
                    label = f"Year: {title}"
                elif group_name == "Month":
                    label = f"Month: {node.get('name') or title}"
                elif group_name == "Week":
                    label = f"Week {title}"
                elif group_name == "Day":
                    label = f"Day: {title}"
                elif group_name == "TimePeriod":
                    label = f"Period: {node.get('value') or title}"
                else:
                    label = str(title)
                node_data = {
                    "id": node_id,
                    "label": label,
                    "group": group_name
                }
                if group_name == "Article":
                    node_data["category"] = node.get("category") or "General"
                    node_data["sentiment"] = node.get("sentiment") or "Neutral"
                nodes.append(node_data)
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

        with self.get_session() as session:
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

            # 4. Fetch time tree branches linked to the articles in this workspace
            res_timetree = session.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                MATCH (tp:TimePeriod)-[r_art:HAS_ARTICLE]->(a)
                MATCH (d:Day)-[r_tp:HAS_PERIOD]->(tp)
                MATCH (w:Week)-[r_d:HAS_DAY]->(d)
                MATCH (m:Month)-[r_w:HAS_WEEK]->(w)
                MATCH (y:Year)-[r_m:HAS_MONTH]->(m)
                RETURN a, tp, r_art, d, r_tp, w, r_d, m, r_w, y, r_m
            """, org_name=org_name)
            
            for record in res_timetree:
                a = record.get("a")
                tp = record.get("tp")
                d = record.get("d")
                w = record.get("w")
                m = record.get("m")
                y = record.get("y")
                
                add_node(y, "Year")
                add_node(m, "Month")
                add_node(w, "Week")
                add_node(d, "Day")
                add_node(tp, "TimePeriod")
                
                if y and m:
                    add_edge(y, m, "HAS_MONTH")
                if m and w:
                    add_edge(m, w, "HAS_WEEK")
                if w and d:
                    add_edge(w, d, "HAS_DAY")
                if d and tp:
                    add_edge(d, tp, "HAS_PERIOD")
                if tp and a:
                    add_edge(tp, a, "HAS_ARTICLE")

        return {"nodes": nodes, "edges": edges}

    def get_shortest_path(self, source_name: str, target_name: str, org_name: str = "Default") -> dict:
        with self.get_session() as session:
            result = session.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (source) WHERE source.name = $source_name OR source.title = $source_name
                MATCH (target) WHERE target.name = $target_name OR target.title = $target_name
                MATCH p = shortestPath((source)-[*..6]-(target))
                WHERE ALL(n IN nodes(p) WHERE 
                    (n:Organization AND n.name = $org_name) OR
                    (n:Article AND size((n)-[:UNDER_WORKSPACE]->(o)) > 0) OR
                    (n:Person AND size((n)-[:MENTIONED_IN]->(:Article)-[:UNDER_WORKSPACE]->(o)) > 0) OR
                    (n:Company AND size((n)-[:MENTIONED_IN]->(:Article)-[:UNDER_WORKSPACE]->(o)) > 0) OR
                    (n:Location AND size((n)-[:MENTIONED_IN]->(:Article)-[:UNDER_WORKSPACE]->(o)) > 0) OR
                    (n:Year OR n:Month OR n:Week OR n:Day OR n:TimePeriod)
                )
                RETURN p
            """, source_name=source_name, target_name=target_name, org_name=org_name)
            
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
                    context_data = get_relationship_context(
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
