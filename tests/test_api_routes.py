import pytest

class TestAPIRoutes:
    def test_read_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "html" in response.headers.get("content-type", "").lower()

    def test_get_organizations(self, client):
        response = client.get("/api/organizations")
        assert response.status_code == 200
        data = response.json()
        assert "organizations" in data
        assert data["organizations"] == ["Default", "Tech"]

    def test_get_stats(self, client):
        response = client.get("/api/stats?org=Default")
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == 5
        assert data["companies"] == 10

    def test_get_recent(self, client):
        response = client.get("/api/recent?org=Default")
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert len(data["articles"]) == 1

    def test_get_graph(self, client):
        response = client.get("/api/graph?org=Default&limit=30")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 1

    def test_get_path(self, client):
        response = client.get("/api/path?source=Elon&target=Tesla&org=Default")
        assert response.status_code == 200
        data = response.json()
        assert "path_found" in data

    def test_consolidate_entities(self, client):
        response = client.post("/api/consolidate?org=Default")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_vacuum_database(self, client):
        response = client.post("/api/vacuum?org=Default")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "space_stats" in data

    def test_get_space_stats(self, client):
        response = client.get("/api/space-stats?org=Default")
        assert response.status_code == 200
        data = response.json()
        assert "total_nodes" in data
        assert data["total_nodes"] == 15

    def test_get_company_financials(self, client):
        response = client.get("/api/company-financials?company=Tesla&org=Default")
        assert response.status_code == 200
        data = response.json()
        assert "stock_quote" in data
        assert "sentiment_summary" in data
        assert "articles" in data

    def test_database_offline_error_handling(self, client, mock_db):
        mock_db.get_organizations.side_effect = Exception("Failed to connect to bolt://localhost:7687: Connection refused")
        response = client.get("/api/organizations")
        assert response.status_code == 503
        assert "Neo4j database is offline" in response.json()["detail"]
