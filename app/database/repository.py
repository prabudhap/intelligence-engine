from app.database import queries

class DatabaseRepository:
    """Facade for Neo4j database operations, delegating domain query logic to sub-modules."""
    def __init__(self, driver=None):
        self.driver = driver

    def get_session(self):
        if not self.driver:
            raise RuntimeError("Neo4j database driver is not initialized or has been closed.")
        return self.driver.session()

    def save_intelligence(self, org_name: str, title: str, entities: dict, body: str = "", pub_date: str | None = None, url: str | None = None):
        return queries.save_intelligence(self, org_name, title, entities, body, pub_date, url)

    def get_organizations(self) -> list:
        return queries.get_organizations(self)

    def get_stats(self, org_name: str) -> dict:
        return queries.get_stats(self, org_name)

    def get_recent_articles(self, org_name: str) -> list:
        return queries.get_recent_articles(self, org_name)

    def get_graph_data(self, org_name: str, limit: int = 30, include_time_tree: bool = False) -> dict:
        return queries.get_graph_data(self, org_name, limit=limit, include_time_tree=include_time_tree)

    def get_shortest_path(self, source_name: str, target_name: str, org_name: str = "Default") -> dict:
        return queries.get_shortest_path(self, source_name, target_name, org_name)

    def deduplicate_entities(self, org_name: str) -> dict:
        return queries.deduplicate_database_entities(self, org_name)

    def vacuum_database(self, org_name: str = "Default", prune_cooccurrences: bool = False, min_cooccurrence_weight: int = 1) -> dict:
        return queries.vacuum_database(self, org_name, prune_cooccurrences=prune_cooccurrences, min_cooccurrence_weight=min_cooccurrence_weight)

    def get_space_stats(self, org_name: str = "Default") -> dict:
        return queries.get_database_space_stats(self, org_name)

    def get_company_related_articles(self, company_name: str, org_name: str = "Default") -> list:
        return queries.get_company_related_articles(self, company_name, org_name)


