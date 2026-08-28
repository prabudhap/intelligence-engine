import pytest
from unittest.mock import patch, MagicMock
from app.extractors.scraper import scrape_article
from app.nlp.classification import classify_topic, analyze_sentiment
from app.nlp import extract_entities
from app.database.queries.graph import get_graph_data
from app.database.queries.pathfinder import get_shortest_path
from app.services.stock_service import resolve_ticker_symbol, fetch_stock_quote

class TestHTMLScraperFunctionality:
    def test_scrape_article_html_parsing(self):
        sample_html = """
        <html>
            <head>
                <title>Tesla Launches New Cybercab in Austin</title>
            </head>
            <body>
                <header><nav>Home Menu</nav></header>
                <article>
                    <p>Tesla announced its new autonomous Cybercab fleet in Austin, Texas today.</p>
                    <p>CEO Elon Musk presented the vehicles during a live presentation at Giga Texas.</p>
                </article>
                <footer>Contact Us</footer>
            </body>
        </html>
        """
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = sample_html
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            result = scrape_article("https://example.com/test-article")

            assert result["title"] == "Tesla Launches New Cybercab in Austin"
            assert "Tesla announced its new autonomous Cybercab" in result["body"]
            assert "Elon Musk presented" in result["body"]
            assert "Home Menu" not in result["body"] # header element decomposed

class TestNLPClassificationFunctionality:
    def test_classify_topic_technology(self):
        text = "NVIDIA unveiled its latest AI GPU architecture with advanced neural processing units."
        assert classify_topic(text) in ["Technology", "Finance"]

    def test_classify_topic_defense(self):
        text = "Military defense radar systems were deployed by Lockheed Martin for air combat security."
        assert classify_topic(text) == "Defense"

    def test_analyze_sentiment_positive(self):
        text = "Quarterly revenue soared by 45 percent, beating all analyst expectations with profit growth."
        assert analyze_sentiment(text) == "Positive"

    def test_analyze_sentiment_negative(self):
        text = "The company faced catastrophic loss, massive layoff, severe lawsuit, and financial crisis."
        assert analyze_sentiment(text) == "Negative"

class TestEntityAndRelationshipExtraction:
    def test_extract_entities_schema(self):
        text = """
        Apple Inc CEO Tim Cook introduced the new iPhone 16 in Cupertino.
        
        Tim Cook highlighted that Apple is investing heavily in California.
        """
        extracted = extract_entities(text)
        
        assert "companies" in extracted
        assert "people" in extracted
        assert "locations" in extracted
        assert "relationships" in extracted
        assert "category" in extracted
        assert "sentiment" in extracted
        
        # Verify schema list types
        assert isinstance(extracted["companies"], list)
        assert isinstance(extracted["people"], list)

class FakeNode(dict):
    def __init__(self, element_id, labels, name):
        super().__init__({"name": name, "title": name})
        self.element_id = element_id
        self.labels = labels

class FakePath:
    def __init__(self, start_node, end_node, nodes, relationships):
        self.start_node = start_node
        self.end_node = end_node
        self.nodes = nodes
        self.relationships = relationships

class TestGraphQueriesFunctionality:
    def test_get_graph_data(self):
        repo = MagicMock()
        session = MagicMock()
        repo.get_session.return_value.__enter__.return_value = session

        # Mock execute_read to return tx query records
        mock_arts = {
            "o_id": "0", "o_name": "Default",
            "art_nodes": [{"id": "a1", "label": "Test Article", "group": "Article"}],
            "art_ids": ["a1"]
        }
        mock_ents = [{"id": "e1", "label": "Tesla", "group": "Company", "a_id": "a1"}]
        mock_pc = []
        mock_pl = []
        mock_co = []
        mock_tt = []

        def mock_execute_read(tx_func):
            tx = MagicMock()
            tx.run.side_effect = [
                MagicMock(single=lambda: mock_arts),
                mock_ents,
                mock_pc,
                mock_pl,
                mock_co,
                mock_tt
            ]
            return tx_func(tx)

        session.execute_read.side_effect = mock_execute_read

        graph = get_graph_data(repo, org_name="Default", limit=30, include_time_tree=False)
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0

    def test_get_shortest_path(self):
        repo = MagicMock()
        session = MagicMock()
        repo.get_session.return_value.__enter__.return_value = session

        mock_node1 = FakeNode("p1", ["Person"], "Elon Musk")
        mock_node2 = FakeNode("c1", ["Company"], "Tesla")

        mock_rel = MagicMock(element_id="r1", type="INDIRECTLY_INVOLVED_WITH")
        mock_rel.get = lambda k, d=None: 1 if k == "weight" else d
        mock_rel.start_node = mock_node1
        mock_rel.end_node = mock_node2

        mock_path = FakePath(start_node=mock_node1, end_node=mock_node2, nodes=[mock_node1, mock_node2], relationships=[mock_rel])

        mock_rec = MagicMock()
        mock_rec.get = lambda k, d=None: mock_path if k == "p" else ["Elon Musk works at Tesla."] if k == "path_bodies" else d

        def mock_execute_read(tx_func):
            tx = MagicMock()
            tx.run.side_effect = [
                MagicMock(single=lambda: mock_rec),
                [] # res_comp
            ]
            return tx_func(tx)

        session.execute_read.side_effect = mock_execute_read

        path = get_shortest_path(repo, source_name="Elon Musk", target_name="Tesla", org_name="Default")
        assert "nodes" in path
        assert "edges" in path
        assert "affected_companies" in path

class TestStockServiceFunctionality:
    def test_resolve_ticker_symbol(self):
        assert resolve_ticker_symbol("Tesla Inc.") == "TSLA"
        assert resolve_ticker_symbol("Apple LLC") == "AAPL"
        assert resolve_ticker_symbol("Microsoft Corp.") == "MSFT"
        assert resolve_ticker_symbol("Google") == "GOOGL"

    def test_fetch_stock_quote_unlisted(self):
        result = fetch_stock_quote("NonExistentPrivateCompany12345")
        assert result["is_public"] is False
        assert result["ticker"] is None

    @patch("httpx.Client.get")
    def test_fetch_stock_quote_mocked_price(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {
                        "regularMarketPrice": 220.50,
                        "previousClose": 215.00,
                        "currency": "USD"
                    }
                }]
            }
        }
        mock_get.return_value = mock_resp

        quote = fetch_stock_quote("Tesla")
        assert quote["is_public"] is True
        assert quote["ticker"] == "TSLA"
        assert quote["current_price"] == 220.50
        assert quote["change_amount"] == 5.50
        assert quote["currency"] == "USD"
        assert quote["is_up"] is True
        assert "$220.50" in quote["formatted_price"]

