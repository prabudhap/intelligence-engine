import pytest
from app.nlp.text_processing import normalize_company_name, clean_entity_name
from app.database.entity_resolution import normalize_name, build_entity_alias_map, consolidate_graph

class TestNLPTextProcessing:
    def test_normalize_company_name_suffixes(self):
        assert normalize_company_name("Tesla Inc.") == "Tesla"
        assert normalize_company_name("Tesla, Inc") == "Tesla"
        assert normalize_company_name("Google LLC") == "Google"
        assert normalize_company_name("Microsoft Corp.") == "Microsoft"
        assert normalize_company_name("Apple Limited") == "Apple"
        assert normalize_company_name("Acme Co.") == "Acme"
        assert normalize_company_name("") == ""
        assert normalize_company_name(None) == ""

    def test_clean_entity_name(self):
        assert clean_entity_name("  elon   musk  ") == "Elon Musk"
        assert clean_entity_name("new york city,") == "New York City"
        assert clean_entity_name("") == ""
        assert clean_entity_name(None) == ""

class TestEntityResolution:
    def test_normalize_name_acronyms(self):
        assert normalize_name("US") == "United States"
        assert normalize_name("U.S.") == "United States"
        assert normalize_name("USA") == "United States"
        assert normalize_name("UK") == "United Kingdom"
        assert normalize_name("EU") == "European Union"
        assert normalize_name("UN") == "United Nations"
        assert normalize_name("'Elon Musk'") == "Elon Musk"

    def test_build_entity_alias_map(self):
        labels = ["Elon Musk", "Elon", "Musk", "Tesla Inc", "Tesla"]
        alias_map = build_entity_alias_map(labels)
        
        assert alias_map["Elon"] == "Elon Musk"
        assert alias_map["Musk"] == "Elon Musk"
        assert alias_map["Elon Musk"] == "Elon Musk"
        assert alias_map["Tesla"] == "Tesla Inc"
        assert alias_map["Tesla Inc"] == "Tesla Inc"

    def test_consolidate_graph_merging(self):
        nodes = [
            {"id": "n1", "label": "Elon Musk", "group": "Person"},
            {"id": "n2", "label": "Elon", "group": "Person"},
            {"id": "n3", "label": "Tesla Inc", "group": "Company"},
        ]
        edges = [
            {"from": "n1", "to": "n3", "label": "INDIRECTLY_INVOLVED_WITH", "weight": 1},
            {"from": "n2", "to": "n3", "label": "INDIRECTLY_INVOLVED_WITH", "weight": 2},
        ]

        cons_nodes, cons_edges = consolidate_graph(nodes, edges)

        # Elon and Elon Musk should be merged into 1 person node
        person_nodes = [n for n in cons_nodes if n.get("group") == "Person"]
        assert len(person_nodes) == 1
        assert person_nodes[0]["label"] == "Elon Musk"

        # Edges between merged person and company should combine weights
        assert len(cons_edges) == 1
        assert cons_edges[0]["weight"] == 3

    def test_consolidate_graph_with_none_label(self):
        nodes = [
            {"id": "n1", "label": None, "group": "Person"},
            {"id": "n2", "label": "Elon Musk", "group": "Person"},
        ]
        edges = []

        cons_nodes, cons_edges = consolidate_graph(nodes, edges)
        assert len(cons_nodes) == 2

