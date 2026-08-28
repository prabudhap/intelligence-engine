from app.database.temporal import extract_context_from_bodies

def _resolve_node_info(node) -> dict:
    """Extracts node ID, display label, and primary group label from a Neo4j node object."""
    label = list(node.labels)[0] if getattr(node, "labels", None) else "Unknown"
    title = node.get("title") or node.get("name") or node.get("id") or node.get("value") or "Unnamed"
    return {
        "id": node.element_id,
        "label": str(title),
        "group": label
    }

def get_shortest_path(repo, source_name: str, target_name: str, org_name: str = "Default") -> dict:
    """Calculates shortest path between two entities and extracts contextual narrative evidence."""
    if source_name == target_name:
        def _tx_single(tx):
            result = tx.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (node) WHERE (node.name = $source_name OR node.title = $source_name OR node.id = $source_name OR node.value = $source_name)
                  AND (
                    node:Organization OR node:Year OR node:Month OR node:Week OR node:Day OR node:TimePeriod OR
                    EXISTS { (node)-[:UNDER_WORKSPACE]->(o) } OR
                    EXISTS { (node)-[:MENTIONED_IN]->(:Article)-[:UNDER_WORKSPACE]->(o) }
                  )
                RETURN node
            """, source_name=source_name, org_name=org_name)
            return result.single()

        with repo.get_session() as session:
            record = session.execute_read(_tx_single)
            if not record or not record.get("node"):
                return {"nodes": [], "edges": []}
            return {
                "nodes": [_resolve_node_info(record.get("node"))],
                "edges": []
            }

    def _tx(tx):
        # 1. Primary path search excluding intermediate Organization and TimeTree hub shortcuts
        res = tx.run("""
            MATCH (o:Organization {name: $org_name})
            MATCH (source) WHERE (source.name = $source_name OR source.title = $source_name OR source.id = $source_name OR source.value = $source_name)
              AND (
                source:Organization OR source:Year OR source:Month OR source:Week OR source:Day OR source:TimePeriod OR
                EXISTS { (source)-[:UNDER_WORKSPACE]->(o) } OR
                EXISTS { (source)-[:MENTIONED_IN]->(:Article)-[:UNDER_WORKSPACE]->(o) }
              )
            MATCH (target) WHERE (target.name = $target_name OR target.title = $target_name OR target.id = $target_name OR target.value = $target_name)
              AND (
                target:Organization OR target:Year OR target:Month OR target:Week OR target:Day OR target:TimePeriod OR
                EXISTS { (target)-[:UNDER_WORKSPACE]->(o) } OR
                EXISTS { (target)-[:MENTIONED_IN]->(:Article)-[:UNDER_WORKSPACE]->(o) }
              )
            MATCH p = shortestPath((source)-[*..6]-(target))
            WHERE (source:Organization OR target:Organization) 
               OR ALL(n IN nodes(p)[1..-1] WHERE NOT (n:Organization OR n:Year OR n:Month OR n:Week OR n:Day OR n:TimePeriod))
            RETURN p, [n IN nodes(p) WHERE n:Article AND n.body IS NOT NULL | n.body] AS path_bodies
        """, source_name=source_name, target_name=target_name, org_name=org_name)
        record = res.single()

        # Fallback to general shortest path if no domain-filtered path exists
        if not record or not record.get("p"):
            res_fallback = tx.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (source) WHERE (source.name = $source_name OR source.title = $source_name OR source.id = $source_name OR source.value = $source_name)
                MATCH (target) WHERE (target.name = $target_name OR target.title = $target_name OR target.id = $target_name OR target.value = $target_name)
                MATCH p = shortestPath((source)-[*..6]-(target))
                RETURN p, [n IN nodes(p) WHERE n:Article AND n.body IS NOT NULL | n.body] AS path_bodies
            """, source_name=source_name, target_name=target_name, org_name=org_name)
            record = res_fallback.single()

        if not record or not record.get("p"):
            return None, [], {}

        path = record.get("p")
        path_bodies = record.get("path_bodies") or []

        # Query affected/mentioned companies for any Article in the path
        article_ids = [n.element_id for n in path.nodes if "Article" in n.labels]
        affected_companies_map = {}
        if article_ids:
            res_comp = tx.run("""
                UNWIND $art_ids AS art_id
                MATCH (a:Article) WHERE elementId(a) = art_id
                OPTIONAL MATCH (c:Company)-[:MENTIONED_IN]->(a)
                RETURN elementId(a) AS art_id,
                       [comp in collect(distinct c) WHERE comp IS NOT NULL | {id: elementId(comp), name: comp.name}] AS company_nodes
            """, art_ids=article_ids)
            for r in res_comp:
                affected_companies_map[r["art_id"]] = r["company_nodes"] or []

        return path, path_bodies, affected_companies_map

    with repo.get_session() as session:
        path, path_bodies, affected_companies_map = session.execute_read(_tx)
        if not path:
            return {"nodes": [], "edges": [], "affected_companies": []}
            
        nodes = []
        edges = []
        seen_nodes = set()
        seen_edges = set()
        all_affected_companies = set()
        
        for node in path.nodes:
            if node.element_id not in seen_nodes:
                nodes.append(_resolve_node_info(node))
                seen_nodes.add(node.element_id)
            
        for rel in path.relationships:
            edge_key = (rel.start_node.element_id, rel.end_node.element_id, rel.type)
            if edge_key not in seen_edges:
                name1 = rel.start_node.get("name") or rel.start_node.get("title") or ""
                name2 = rel.end_node.get("name") or rel.end_node.get("title") or ""
                context_data = extract_context_from_bodies(path_bodies, name1, name2)
                
                # Check if start or end node is an Article with affected companies
                start_comps = [c["name"] for c in affected_companies_map.get(rel.start_node.element_id, [])]
                end_comps = [c["name"] for c in affected_companies_map.get(rel.end_node.element_id, [])]
                edge_comps = list(set(start_comps + end_comps))
                
                edges.append({
                    "from": rel.start_node.element_id,
                    "to": rel.end_node.element_id,
                    "label": rel.type,
                    "context": context_data.get("context", ""),
                    "full_context": context_data.get("full_context", ""),
                    "affected_companies": edge_comps
                })
                seen_edges.add(edge_key)

        # Inject Affected Company nodes & edges into the graph
        for art_id, company_list in affected_companies_map.items():
            for comp in company_list:
                c_id = comp["id"]
                c_name = comp["name"]
                all_affected_companies.add(c_name)
                
                # Add the Company node
                if c_id not in seen_nodes:
                    nodes.append({
                        "id": c_id,
                        "label": c_name,
                        "group": "Company"
                    })
                    seen_nodes.add(c_id)
                
                # Add relationship from Company to Article
                edge_key = (c_id, art_id, "MENTIONED_IN")
                if edge_key not in seen_edges:
                    edges.append({
                        "from": c_id,
                        "to": art_id,
                        "label": "AFFECTED_COMPANY"
                    })
                    seen_edges.add(edge_key)
            
        return {
            "nodes": nodes,
            "edges": edges,
            "affected_companies": sorted(list(all_affected_companies))
        }
