import pytest
from unittest.mock import MagicMock
from app.database.temporal import get_temporal_info, extract_context_from_text
from app.database.queries.maintenance import purge_orphan_nodes, prune_low_weight_cooccurrences, get_database_space_stats

class TestTemporalUtils:
    def test_get_temporal_info_valid_date(self):
        info = get_temporal_info("Mon, 24 Aug 2026 14:00:00 GMT")
        assert info["year"] == 2026
        assert info["month"] == 8
        assert info["month_name"] == "August"
        assert info["period"] == "12:00-18:00"
        assert info["year_id"] == "2026"
        assert info["month_id"] == "2026-08"

    def test_get_temporal_info_fallback(self):
        info = get_temporal_info(None)
        assert info["year"] >= 2026
        assert "year_id" in info

    def test_extract_context_from_text(self):
        body = "Elon Musk visited the Tesla gigafactory today.\n\nTesla is expanding in Austin."
        res = extract_context_from_text(body, "Elon Musk", "Tesla")
        assert "Elon Musk visited the Tesla" in res["context"]
        assert res["full_context"] == "Elon Musk visited the Tesla gigafactory today."

class TestMaintenanceQueries:
    def test_purge_orphan_nodes(self):
        repo = MagicMock()
        session = MagicMock()
        repo.get_session.return_value.__enter__.return_value = session
        
        # Mock single() for query 1 and 2
        mock_rec1 = {"cnt": 3}
        mock_rec2 = {"cnt": 2}
        session.run.side_effect = [
            MagicMock(single=lambda: mock_rec1),
            MagicMock(single=lambda: mock_rec2),
            None, None, None, None # cascade unlinked runs
        ]

        res = purge_orphan_nodes(repo, "Default")
        assert res["purged_entities"] == 3
        assert res["purged_time_nodes"] == 2
        assert res["total_purged_nodes"] == 5

    def test_prune_low_weight_cooccurrences(self):
        repo = MagicMock()
        session = MagicMock()
        repo.get_session.return_value.__enter__.return_value = session
        
        session.run.return_value.single.return_value = {"cnt": 7}

        res = prune_low_weight_cooccurrences(repo, max_weight=1)
        assert res["pruned_cooccurrence_edges"] == 7

    def test_get_database_space_stats(self):
        repo = MagicMock()
        session = MagicMock()
        repo.get_session.return_value.__enter__.return_value = session

        session.run.side_effect = [
            MagicMock(single=lambda: {"cnt": 100}), # total_nodes
            MagicMock(single=lambda: {"cnt": 250}), # total_rels
            MagicMock(single=lambda: {"cnt": 20}),  # articles
            MagicMock(single=lambda: {"cnt": 40}),  # people
            MagicMock(single=lambda: {"cnt": 15}),  # companies
            MagicMock(single=lambda: {"cnt": 10}),  # locations
            MagicMock(single=lambda: {"cnt": 50}),  # co_occurrences
            MagicMock(single=lambda: {"cnt": 5}),   # orphan_entities
        ]

        stats = get_database_space_stats(repo, "Default")
        assert stats["total_nodes"] == 100
        assert stats["total_relationships"] == 250
        assert stats["articles_count"] == 20
        assert stats["orphan_entities_count"] == 5
