from typing import cast, LiteralString
from neo4j import GraphDatabase

from app.core import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, logger
from app.database.repository import DatabaseRepository

class Database(DatabaseRepository):
    def __init__(self):
        super().__init__(driver=None)
        self.connect()

    def connect(self):
        if self.driver is None:
            try:
                self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            except Exception as e:
                logger.error(f"Failed to create Neo4j driver connection: {e}")
                self.driver = None

    def get_session(self):
        if self.driver is None:
            self.connect()
        return super().get_session()

    def close(self):
        if self.driver is not None:
            try:
                self.driver.close()
            except Exception as e:
                logger.warning(f"Error while closing Neo4j driver: {e}")
            finally:
                self.driver = None

    def _execute_ddl(self, session, primary_cypher: str, fallback_cypher: str, name: str):
        """Executes a DDL statement with Neo4j 5 syntax and fallback to legacy Neo4j 4.x syntax."""
        try:
            session.run(cast(LiteralString, primary_cypher))
        except Exception as e:
            logger.warning(f"Neo4j 5 DDL execution failed for {name}: {e}. Retrying with legacy syntax...")
            try:
                session.run(cast(LiteralString, fallback_cypher))
            except Exception as e2:
                logger.error(f"Legacy DDL fallback failed for {name}: {e2}")

    def setup_constraints(self):
        try:
            with self.get_session() as session:
                session.run("RETURN 1")
        except Exception as e:
            logger.warning(f"Neo4j database connection test failed; skipping constraint setup: {e}")
            return

        constraints = [
            ("org_name_unique", "Organization", "name"),
            ("article_title_unique", "Article", "title"),
            ("person_name_unique", "Person", "name"),
            ("company_name_unique", "Company", "name"),
            ("location_name_unique", "Location", "name"),
            ("year_id_unique", "Year", "id"),
            ("month_id_unique", "Month", "id"),
            ("week_id_unique", "Week", "id"),
            ("day_id_unique", "Day", "id"),
            ("timeperiod_id_unique", "TimePeriod", "id"),
        ]
        
        try:
            with self.get_session() as session:
                for c_name, label, prop in constraints:
                    p_query = f"CREATE CONSTRAINT {c_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    f_query = f"CREATE CONSTRAINT {c_name} IF NOT EXISTS ON (n:{label}) ASSERT n.{prop} IS UNIQUE"
                    self._execute_ddl(session, p_query, f_query, c_name)
                    
                # Indexes
                self._execute_ddl(
                    session,
                    "CREATE INDEX article_created_at_idx IF NOT EXISTS FOR (a:Article) ON (a.created_at)",
                    "CREATE INDEX article_created_at_idx IF NOT EXISTS ON :Article(created_at)",
                    "article_created_at_idx"
                )
                self._execute_ddl(
                    session,
                    "CREATE INDEX article_url_idx IF NOT EXISTS FOR (a:Article) ON (a.url)",
                    "CREATE INDEX article_url_idx IF NOT EXISTS ON :Article(url)",
                    "article_url_idx"
                )
        except Exception as e:
            logger.warning(f"Error during database DDL initialization: {e}")

