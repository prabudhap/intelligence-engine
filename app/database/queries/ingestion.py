from typing import Any
from app.database.temporal import get_temporal_info
from app.database.entity_resolution import build_entity_alias_map

def save_intelligence(repo, org_name: str, title: str, entities: dict, body: str = "", pub_date: str | None = None, url: str | None = None):
    """Saves ingested article and extracted entity graph to Neo4j."""
    with repo.get_session() as session:
        session.execute_write(_cypher_transaction, org_name, title, entities, body, pub_date, url)

def _canonicalize_names(raw_names: list[str]) -> tuple[dict[str, str], list[str]]:
    """Cleans raw names, builds alias mapping, and returns canonical sorted name list."""
    cleaned = [n.strip() for n in raw_names if n and isinstance(n, str) and n.strip()]
    alias_map = build_entity_alias_map(cleaned)
    canonical_list = sorted(list(set([alias_map.get(n, n) for n in cleaned])))
    return alias_map, canonical_list

def _deduplicate_relationships(raw_rels: list[dict], k1: str, k2: str, map1: dict, map2: dict) -> list[dict]:
    """Deduplicates and sorts relationship pairs after applying canonical name resolution."""
    seen = set()
    result = []
    for r in raw_rels:
        v1 = map1.get(r.get(k1, "").strip(), r.get(k1, "").strip()) if r.get(k1) else ""
        v2 = map2.get(r.get(k2, "").strip(), r.get(k2, "").strip()) if r.get(k2) else ""
        if v1 and v2 and (v1, v2) not in seen:
            seen.add((v1, v2))
            result.append({k1: v1, k2: v2})
    result.sort(key=lambda x: (x[k1], x[k2]))
    return result

def _cypher_transaction(tx: Any, org_name: str, title: str, entities: dict, body: str, pub_date: str | None = None, url: str | None = None):
    temp_info = get_temporal_info(pub_date)
    current_time = temp_info["timestamp"]
    category = entities.get("category", "General")
    sentiment = entities.get("sentiment", "Neutral")
    
    # Entity Resolution & Alias Consolidation
    company_map, companies = _canonicalize_names(entities.get("companies", []))
    people_map, people = _canonicalize_names(entities.get("people", []))
    location_map, locations = _canonicalize_names(entities.get("locations", []))

    # Deduplicate relationship pairs with resolved canonical names
    relationships = _deduplicate_relationships(
        entities.get("relationships", []), "person", "company", people_map, company_map
    )
    location_relationships = _deduplicate_relationships(
        entities.get("location_relationships", []), "person", "location", people_map, location_map
    )

    # Pairwise co-occurrences for entities mentioned in this article
    all_ents = []
    for p in people: all_ents.append({"name": p, "group": "Person"})
    for c in companies: all_ents.append({"name": c, "group": "Company"})
    for l in locations: all_ents.append({"name": l, "group": "Location"})

    co_occurrences = []
    seen_co = set()
    for i in range(len(all_ents)):
        for j in range(i + 1, len(all_ents)):
            e1, e2 = all_ents[i], all_ents[j]
            if e1["name"] != e2["name"]:
                pair_key = tuple(sorted([e1["name"], e2["name"]]))
                if pair_key not in seen_co:
                    seen_co.add(pair_key)
                    co_occurrences.append({
                        "p1": pair_key[0],
                        "p2": pair_key[1]
                    })

    query = """
    MERGE (o:Organization {name: $org_name})

    MERGE (y:Year {id: $temp.year_id})
    ON CREATE SET y.value = $temp.year
    MERGE (m:Month {id: $temp.month_id})
    ON CREATE SET m.value = $temp.month, m.name = $temp.month_name
    MERGE (y)-[:HAS_MONTH]->(m)
    MERGE (w:Week {id: $temp.week_id})
    ON CREATE SET w.value = $temp.week
    MERGE (m)-[:HAS_WEEK]->(w)
    MERGE (d:Day {id: $temp.day_id})
    ON CREATE SET d.value = $temp.day
    MERGE (w)-[:HAS_DAY]->(d)
    MERGE (tp:TimePeriod {id: $temp.period_id})
    ON CREATE SET tp.value = $temp.period
    MERGE (d)-[:HAS_PERIOD]->(tp)

    MERGE (a:Article {title: $title})
    ON CREATE SET a.created_at = $created_at, a.body = $body, a.category = $category, a.sentiment = $sentiment, a.url = $url
    ON MATCH SET a.body = $body, a.category = $category, a.sentiment = $sentiment, a.url = $url

    MERGE (tp)-[:HAS_ARTICLE]->(a)
    MERGE (a)-[:UNDER_WORKSPACE]->(o)

    WITH a
    FOREACH (company_name IN $companies |
        MERGE (c:Company {name: company_name})
        MERGE (c)-[:MENTIONED_IN]->(a)
    )
    FOREACH (person_name IN $people |
        MERGE (p:Person {name: person_name})
        MERGE (p)-[:MENTIONED_IN]->(a)
    )
    FOREACH (loc_name IN $locations |
        MERGE (l:Location {name: loc_name})
        MERGE (l)-[:MENTIONED_IN]->(a)
    )
    FOREACH (rel IN $relationships |
        MERGE (p2:Person {name: rel.person})
        MERGE (c2:Company {name: rel.company})
        MERGE (p2)-[r:INDIRECTLY_INVOLVED_WITH]->(c2)
        ON CREATE SET r.weight = 1, r.last_seen = $created_at
        ON MATCH SET r.weight = coalesce(r.weight, 1) + 1, r.last_seen = $created_at
    )
    FOREACH (rel IN $location_relationships |
        MERGE (p3:Person {name: rel.person})
        MERGE (l3:Location {name: rel.location})
        MERGE (p3)-[r2:LOCATED_IN]->(l3)
        ON CREATE SET r2.weight = 1, r2.last_seen = $created_at
        ON MATCH SET r2.weight = coalesce(r2.weight, 1) + 1, r2.last_seen = $created_at
    )
    FOREACH (co IN $co_occurrences |
        MERGE (e1 {name: co.p1})
        MERGE (e2 {name: co.p2})
        MERGE (e1)-[r3:CO_OCCURRED_WITH]->(e2)
        ON CREATE SET r3.weight = 1, r3.last_seen = $created_at
        ON MATCH SET r3.weight = coalesce(r3.weight, 1) + 1, r3.last_seen = $created_at
    )
    """
    tx.run(query, 
           org_name=org_name, 
           temp=temp_info, 
           title=title, 
           created_at=current_time, 
           body=body, 
           category=category, 
           sentiment=sentiment, 
           url=url, 
           companies=companies, 
           people=people, 
           locations=locations, 
           relationships=relationships, 
           location_relationships=location_relationships,
           co_occurrences=co_occurrences)

def deduplicate_database_entities(repo, org_name: str) -> dict:
    """
    Scans existing entity nodes in Neo4j for the workspace and merges duplicate alias nodes
    (e.g., merging (:Person {name: 'Elon'}) into (:Person {name: 'Elon Musk'})).
    """
    merged_count = 0
    with repo.get_session() as session:
        def _tx(tx):
            nonlocal merged_count
            for label_name in ["Person", "Company", "Location"]:
                res = tx.run(f"""
                    MATCH (o:Organization {{name: $org_name}})
                    MATCH (a:Article)-[:UNDER_WORKSPACE]->(o)
                    MATCH (e:{label_name})-[:MENTIONED_IN]->(a)
                    RETURN distinct e.name as name
                """, org_name=org_name)
                names = [r["name"] for r in res if r.get("name")]
                if not names:
                    continue

                alias_map = build_entity_alias_map(names)
                for alias_name, canon_name in alias_map.items():
                    if alias_name != canon_name and alias_name and canon_name:
                        tx.run(f"""
                            MATCH (alias:{label_name} {{name: $alias_name}})
                            MERGE (canon:{label_name} {{name: $canon_name}})
                            WITH alias, canon
                            MATCH (alias)-[r:MENTIONED_IN]->(a:Article)
                            MERGE (canon)-[:MENTIONED_IN]->(a)
                            WITH alias, canon
                            OPTIONAL MATCH (alias)-[r2:INDIRECTLY_INVOLVED_WITH]->(c:Company)
                            FOREACH (_ IN CASE WHEN r2 IS NOT NULL THEN [1] ELSE [] END |
                                MERGE (canon)-[:INDIRECTLY_INVOLVED_WITH]->(c)
                            )
                            WITH alias, canon
                            OPTIONAL MATCH (alias)-[r3:LOCATED_IN]->(l:Location)
                            FOREACH (_ IN CASE WHEN r3 IS NOT NULL THEN [1] ELSE [] END |
                                MERGE (canon)-[:LOCATED_IN]->(l)
                            )
                            DETACH DELETE alias
                        """, alias_name=alias_name, canon_name=canon_name)
                        merged_count += 1
        session.execute_write(_tx)
    return {"status": "success", "merged_entities_count": merged_count}
