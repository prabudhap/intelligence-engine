from app.database.entity_resolution import consolidate_graph

def get_graph_data(repo, org_name: str, limit: int = 30, include_time_tree: bool = False) -> dict:
    """
    Retrieves interactive network graph nodes and edges for a workspace.
    Optimized with node capping (limit) and entity resolution consolidation.
    """
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()

    def add_n(node_id: str | None, label: str | None, group: str, cat: str | None = None, sent: str | None = None):
        if not node_id:
            return
        if node_id not in seen_nodes:
            item = {"id": node_id, "label": label or "Unnamed", "group": group}
            if cat:
                item["category"] = cat
            if sent:
                item["sentiment"] = sent
            nodes.append(item)
            seen_nodes.add(node_id)

    def add_e(src_id: str | None, dst_id: str | None, rel_type: str, weight: int = 1):
        if not src_id or not dst_id or not rel_type:
            return
        key = (src_id, dst_id, rel_type)
        if key not in seen_edges:
            edges.append({"from": src_id, "to": dst_id, "label": rel_type, "weight": weight})
            seen_edges.add(key)

    with repo.get_session() as session:
        def _tx(tx):
            res_arts = tx.run("""
                MATCH (o:Organization {name: $org_name})
                OPTIONAL MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                WITH o, a ORDER BY a.created_at DESC
                WITH o, collect(distinct a)[0..$limit] as articles
                RETURN elementId(o) as o_id, o.name as o_name, 
                       [art IN articles WHERE art IS NOT NULL | {id: elementId(art), label: art.title, group: "Article", category: coalesce(art.category, "General"), sentiment: coalesce(art.sentiment, "Neutral")}] as art_nodes,
                       [art IN articles WHERE art IS NOT NULL | elementId(art)] as art_ids
            """, org_name=org_name, limit=limit).single()
            
            art_ids = arts_record_ids = []
            if res_arts and res_arts.get("art_ids"):
                art_ids = res_arts.get("art_ids")

            res_ents = tx.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                WHERE elementId(a) IN $art_ids
                MATCH (ent)-[:MENTIONED_IN]->(a)
                RETURN elementId(ent) as id, coalesce(ent.name, ent.title, ent.id, ent.value, "Unnamed") as label, labels(ent)[0] as group, elementId(a) as a_id
            """, org_name=org_name, art_ids=art_ids)
            
            res_pc = tx.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                WHERE elementId(a) IN $art_ids
                MATCH (p:Person)-[:MENTIONED_IN]->(a)
                MATCH (c:Company)-[:MENTIONED_IN]->(a)
                MATCH (p)-[r:INDIRECTLY_INVOLVED_WITH]->(c)
                RETURN elementId(p) as p_id, coalesce(p.name, p.title, "Unnamed") as p_name, elementId(c) as c_id, coalesce(c.name, c.title, "Unnamed") as c_name, coalesce(r.weight, 1) as weight
            """, org_name=org_name, art_ids=art_ids)
            
            res_pl = tx.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                WHERE elementId(a) IN $art_ids
                MATCH (p:Person)-[:MENTIONED_IN]->(a)
                MATCH (l:Location)-[:MENTIONED_IN]->(a)
                MATCH (p)-[r:LOCATED_IN]->(l)
                RETURN elementId(p) as p_id, coalesce(p.name, p.title, "Unnamed") as p_name, elementId(l) as l_id, coalesce(l.name, l.title, "Unnamed") as l_name, coalesce(r.weight, 1) as weight
            """, org_name=org_name, art_ids=art_ids)

            res_co = tx.run("""
                MATCH (o:Organization {name: $org_name})
                MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                WHERE elementId(a) IN $art_ids
                MATCH (e1)-[:MENTIONED_IN]->(a)
                MATCH (e2)-[:MENTIONED_IN]->(a)
                WHERE elementId(e1) < elementId(e2) AND NOT (e1:Article OR e2:Article OR e1:Organization OR e2:Organization)
                MATCH (e1)-[r:CO_OCCURRED_WITH]->(e2)
                RETURN elementId(e1) as e1_id, coalesce(e1.name, "Unnamed") as e1_name, labels(e1)[0] as e1_group,
                       elementId(e2) as e2_id, coalesce(e2.name, "Unnamed") as e2_name, labels(e2)[0] as e2_group,
                       coalesce(r.weight, 1) as weight
            """, org_name=org_name, art_ids=art_ids)
            
            timetree = []
            if include_time_tree and art_ids:
                res_tt = tx.run("""
                    MATCH (o:Organization {name: $org_name})
                    MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                    WHERE elementId(a) IN $art_ids
                    MATCH (tp:TimePeriod)-[:HAS_ARTICLE]->(a)
                    MATCH (d:Day)-[:HAS_PERIOD]->(tp)
                    MATCH (w:Week)-[:HAS_DAY]->(d)
                    MATCH (m:Month)-[:HAS_WEEK]->(w)
                    MATCH (y:Year)-[:HAS_MONTH]->(m)
                    RETURN elementId(y) as y_id, y.value as y_val,
                           elementId(m) as m_id, m.name as m_name, m.value as m_val,
                           elementId(w) as w_id, w.value as w_val,
                           elementId(d) as d_id, d.value as d_val,
                           elementId(tp) as tp_id, tp.value as tp_val,
                           elementId(a) as a_id
                """, org_name=org_name, art_ids=art_ids)
                timetree = list(res_tt)
            
            return res_arts, list(res_ents), list(res_pc), list(res_pl), list(res_co), timetree

        arts_record, entities, pc_rels, pl_rels, co_rels, timetree = session.execute_read(_tx)

        if arts_record:
            o_id = arts_record.get("o_id")
            o_name = arts_record.get("o_name")
            add_n(o_id, o_name, "Organization")
            for art in arts_record.get("art_nodes") or []:
                if art and art.get("id"):
                    add_n(art["id"], art["label"], art["group"], art.get("category"), art.get("sentiment"))
                    add_e(art["id"], o_id, "UNDER_WORKSPACE")

        for rec in entities:
            ent_id = rec.get("id")
            a_id = rec.get("a_id")
            if ent_id:
                add_n(ent_id, rec.get("label"), rec.get("group") or "Unknown")
                if a_id:
                    add_e(ent_id, a_id, "MENTIONED_IN")

        for rec in pc_rels:
            p_id, c_id = rec.get("p_id"), rec.get("c_id")
            weight = rec.get("weight", 1)
            if p_id and c_id:
                add_n(p_id, rec.get("p_name"), "Person")
                add_n(c_id, rec.get("c_name"), "Company")
                add_e(p_id, c_id, "INDIRECTLY_INVOLVED_WITH", weight=weight)

        for rec in pl_rels:
            p_id, l_id = rec.get("p_id"), rec.get("l_id")
            weight = rec.get("weight", 1)
            if p_id and l_id:
                add_n(p_id, rec.get("p_name"), "Person")
                add_n(l_id, rec.get("l_name"), "Location")
                add_e(p_id, l_id, "LOCATED_IN", weight=weight)

        for rec in co_rels:
            e1_id, e2_id = rec.get("e1_id"), rec.get("e2_id")
            weight = rec.get("weight", 1)
            if e1_id and e2_id:
                add_n(e1_id, rec.get("e1_name"), rec.get("e1_group") or "Unknown")
                add_n(e2_id, rec.get("e2_name"), rec.get("e2_group") or "Unknown")
                add_e(e1_id, e2_id, "CO_OCCURRED_WITH", weight=weight)

        for rec in timetree:
            y_id, m_id, w_id, d_id, tp_id, a_id = rec.get("y_id"), rec.get("m_id"), rec.get("w_id"), rec.get("d_id"), rec.get("tp_id"), rec.get("a_id")
            if y_id: add_n(y_id, f"Year: {rec.get('y_val')}", "Year")
            if m_id: add_n(m_id, f"Month: {rec.get('m_name') or rec.get('m_val')}", "Month")
            if w_id: add_n(w_id, f"Week {rec.get('w_val')}", "Week")
            if d_id: add_n(d_id, f"Day: {rec.get('d_val')}", "Day")
            if tp_id: add_n(tp_id, f"Period: {rec.get('tp_val')}", "TimePeriod")

            if y_id and m_id: add_e(y_id, m_id, "HAS_MONTH")
            if m_id and w_id: add_e(m_id, w_id, "HAS_WEEK")
            if w_id and d_id: add_e(w_id, d_id, "HAS_DAY")
            if d_id and tp_id: add_e(d_id, tp_id, "HAS_PERIOD")
            if tp_id and a_id: add_e(tp_id, a_id, "HAS_ARTICLE")

    consolidated_nodes, consolidated_edges = consolidate_graph(nodes, edges)
    return {"nodes": consolidated_nodes, "edges": consolidated_edges}
