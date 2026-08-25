from typing import Any
from app.database.queries.ingestion import deduplicate_database_entities

def purge_orphan_nodes(repo, org_name: str = "Default") -> dict:
    """
    Purges entity nodes (Person, Company, Location) and time-hierarchy nodes 
    that are no longer connected to any active relationships or articles.
    """
    purged_entities = 0
    purged_time_nodes = 0
    
    with repo.get_session() as session:
        # 1. Purge disconnected Person, Company, Location nodes
        res1 = session.run("""
            MATCH (n)
            WHERE (n:Person OR n:Company OR n:Location) AND NOT (n)--()
            DELETE n
            RETURN count(n) AS cnt
        """)
        rec1 = res1.single()
        if rec1:
            purged_entities += rec1["cnt"]

        # 2. Purge TimePeriod nodes not attached to any Article
        res2 = session.run("""
            MATCH (tp:TimePeriod)
            WHERE NOT (tp)-[:HAS_ARTICLE]->()
            DETACH DELETE tp
            RETURN count(tp) AS cnt
        """)
        rec2 = res2.single()
        if rec2:
            purged_time_nodes += rec2["cnt"]

        # 3. Clean up cascade unlinked Day, Week, Month, Year nodes
        session.run("MATCH (d:Day) WHERE NOT (d)-[:HAS_PERIOD]->() DETACH DELETE d")
        session.run("MATCH (w:Week) WHERE NOT (w)-[:HAS_DAY]->() DETACH DELETE w")
        session.run("MATCH (m:Month) WHERE NOT (m)-[:HAS_WEEK]->() DETACH DELETE m")
        session.run("MATCH (y:Year) WHERE NOT (y)-[:HAS_MONTH]->() DETACH DELETE y")

    return {
        "purged_entities": purged_entities,
        "purged_time_nodes": purged_time_nodes,
        "total_purged_nodes": purged_entities + purged_time_nodes
    }

def prune_low_weight_cooccurrences(repo, max_weight: int = 1) -> dict:
    """
    Prunes transient pairwise co-occurrence edges (CO_OCCURRED_WITH) 
    where relationship weight is less than or equal to max_weight.
    """
    pruned_count = 0
    with repo.get_session() as session:
        res = session.run("""
            MATCH ()-[r:CO_OCCURRED_WITH]->()
            WHERE r.weight <= $max_weight
            DELETE r
            RETURN count(r) AS cnt
        """, max_weight=max_weight)
        rec = res.single()
        if rec:
            pruned_count = rec["cnt"]
            
    return {"pruned_cooccurrence_edges": pruned_count}

def get_database_space_stats(repo, org_name: str = "Default") -> dict:
    """
    Returns node, relationship, entity, and storage breakdown for the database.
    """
    with repo.get_session() as session:
        total_nodes = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        
        articles = session.run("MATCH (a:Article) RETURN count(a) AS cnt").single()["cnt"]
        people = session.run("MATCH (p:Person) RETURN count(p) AS cnt").single()["cnt"]
        companies = session.run("MATCH (c:Company) RETURN count(c) AS cnt").single()["cnt"]
        locations = session.run("MATCH (l:Location) RETURN count(l) AS cnt").single()["cnt"]
        
        co_occurrences = session.run("MATCH ()-[r:CO_OCCURRED_WITH]->() RETURN count(r) AS cnt").single()["cnt"]
        
        orphan_entities = session.run("""
            MATCH (n)
            WHERE (n:Person OR n:Company OR n:Location) AND NOT (n)--()
            RETURN count(n) AS cnt
        """).single()["cnt"]

    return {
        "total_nodes": total_nodes,
        "total_relationships": total_rels,
        "articles_count": articles,
        "people_count": people,
        "companies_count": companies,
        "locations_count": locations,
        "co_occurrences_count": co_occurrences,
        "orphan_entities_count": orphan_entities
    }

def vacuum_database(repo, org_name: str = "Default", prune_cooccurrences: bool = False, min_cooccurrence_weight: int = 1) -> dict:
    """
    Runs a full database vacuum cycle:
    1. Alias deduplication & node merging
    2. Orphan node purging
    3. Optional low-weight co-occurrence edge pruning
    4. Gathers post-vacuum space metrics
    """
    # 1. Alias deduplication
    dedup_res = deduplicate_database_entities(repo, org_name)
    
    # 2. Purge orphans
    purge_res = purge_orphan_nodes(repo, org_name)
    
    # 3. Optional co-occurrence pruning
    prune_res = {}
    if prune_cooccurrences:
        prune_res = prune_low_weight_cooccurrences(repo, max_weight=min_cooccurrence_weight)
        
    # 4. Post-vacuum stats
    stats = get_database_space_stats(repo, org_name)
    
    return {
        "status": "success",
        "deduplication": dedup_res,
        "purged_orphans": purge_res,
        "pruned_cooccurrences": prune_res,
        "space_stats": stats
    }
