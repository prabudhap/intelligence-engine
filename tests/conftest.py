import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import db

@pytest.fixture
def mock_db(monkeypatch):
    """Fixture providing a mocked DatabaseRepository instance."""
    mock_repo = MagicMock()
    mock_repo.get_organizations.return_value = ["Default", "Tech"]
    mock_repo.get_stats.return_value = {
        "articles": 5,
        "companies": 10,
        "people": 8,
        "locations": 4,
        "co_occurrences": 12
    }
    mock_repo.get_recent_articles.return_value = [
        {"title": "Test Article", "category": "Tech", "created_at": "2026-08-25T00:00:00Z", "url": "https://example.com"}
    ]
    mock_repo.get_graph_data.return_value = {
        "nodes": [{"id": "a1", "label": "Test Article", "group": "Article"}],
        "edges": []
    }
    mock_repo.get_shortest_path.return_value = {"nodes": [], "edges": [], "path_found": False}
    mock_repo.deduplicate_entities.return_value = {"merged_count": 2, "status": "completed"}
    mock_repo.vacuum_database.return_value = {
        "status": "success",
        "deduplication": {"merged_count": 0},
        "purged_orphans": {"purged_entities": 1, "purged_time_nodes": 0, "total_purged_nodes": 1},
        "pruned_cooccurrences": {},
        "space_stats": {"total_nodes": 10, "total_relationships": 12}
    }
    mock_repo.get_space_stats.return_value = {
        "total_nodes": 15,
        "total_relationships": 20,
        "articles_count": 5,
        "people_count": 4,
        "companies_count": 3,
        "locations_count": 2,
        "co_occurrences_count": 8,
        "orphan_entities_count": 1
    }
    mock_repo.get_company_related_articles.return_value = [
        {"title": "Test Article", "sentiment": "Positive", "url": "https://example.com"}
    ]
    return mock_repo

@pytest.fixture
def client(mock_db, monkeypatch):
    """FastAPI TestClient with mocked database operations."""
    monkeypatch.setattr("app.api.graph.db", mock_db)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
