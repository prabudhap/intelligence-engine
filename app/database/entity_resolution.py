import json
import re
from pathlib import Path

def load_acronym_map(file_path: str | Path | None = None) -> dict[str, str]:
    """Loads acronym mapping dictionary from a JSON resource file."""
    path = Path(file_path) if file_path else Path(__file__).parent.parent / "resources" / "acronym_map.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

ACRONYM_MAP = load_acronym_map()


def normalize_name(name: str) -> str:
    """Cleans whitespace, trailing quotes/commas, and normalizes standard acronyms."""
    if not name:
        return ""
    clean = name.strip()
    if clean in ACRONYM_MAP:
        return ACRONYM_MAP[clean]
    # Remove leading/trailing quotes, commas, periods
    clean = re.sub(r'^[\'\"\,]+|[\'\"\,]+$', '', clean).strip()
    return clean

def build_entity_alias_map(labels: list[str]) -> dict[str, str]:
    """
    Builds a canonical mapping for entity name aliases.
    Sorts longest names first so 'Elon Musk' becomes the canonical target for 'Elon' or 'Musk'.
    
    Example: ["Elon Musk", "Elon", "Musk", "Tesla Inc", "Tesla"]
    Returns: {
        "Elon": "Elon Musk",
        "Musk": "Elon Musk",
        "Elon Musk": "Elon Musk",
        "Tesla": "Tesla Inc",
        "Tesla Inc": "Tesla Inc"
    }
    """
    cleaned_unique = list(set([normalize_name(l) for l in labels if l and isinstance(l, str) and l.strip()]))
    # Sort longest name first so full descriptive names become canonical targets
    sorted_names = sorted(cleaned_unique, key=lambda x: len(x), reverse=True)

    mapping = {}
    canonicals = []

    for name in sorted_names:
        if not name:
            continue
        mapped = None
        for canon in canonicals:
            # Check full word-boundary substring match (e.g. "Elon" inside "Elon Musk")
            pattern = r'\b' + re.escape(name) + r'\b'
            if re.search(pattern, canon, re.IGNORECASE):
                mapped = canon
                break
        
        if mapped:
            mapping[name] = mapped
        else:
            canonicals.append(name)
            mapping[name] = name

    # Also map uncleaned raw labels
    result = {}
    for raw in labels:
        if not raw:
            result[raw] = ""
            continue
        norm = normalize_name(raw)
        result[raw] = mapping.get(norm, norm if norm else raw)

    return result

def consolidate_graph(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Deduplicates graph nodes and consolidates edges based on entity alias resolution.
    Executes per group type ('Person', 'Company', 'Location').
    """
    if not nodes:
        return [], []

    # Group entity labels by group type
    group_labels = {}
    node_by_id = {}
    for n in nodes:
        node_by_id[n["id"]] = n
        grp = n.get("group")
        if grp in ("Person", "Company", "Location"):
            group_labels.setdefault(grp, []).append(n.get("label") or "")

    # Build canonical name mappings per group
    label_to_canonical = {}
    for grp, lbls in group_labels.items():
        mapping = build_entity_alias_map(lbls)
        label_to_canonical.update(mapping)

    # Map node_id -> canonical_node_id
    canonical_nodes_by_group = {}
    id_to_canonical_id = {}

    for n in nodes:
        nid = n["id"]
        grp = n.get("group")
        lbl = n.get("label") or ""

        if grp in ("Person", "Company", "Location"):
            canon_name = label_to_canonical.get(lbl) or lbl or ""
            key = (grp, canon_name.lower())

            if key not in canonical_nodes_by_group:
                # Update node label to canonical name
                n["label"] = canon_name
                canonical_nodes_by_group[key] = nid
                id_to_canonical_id[nid] = nid
            else:
                target_id = canonical_nodes_by_group[key]
                id_to_canonical_id[nid] = target_id
        else:
            id_to_canonical_id[nid] = nid

    # Filter unique canonical nodes
    consolidated_nodes = []
    seen_node_ids = set()
    for n in nodes:
        canon_id = id_to_canonical_id[n["id"]]
        if canon_id not in seen_node_ids:
            seen_node_ids.add(canon_id)
            rep_node = node_by_id[canon_id]
            grp = rep_node.get("group")
            lbl = rep_node.get("label") or ""
            if grp in ("Person", "Company", "Location") and lbl in label_to_canonical:
                rep_node["label"] = label_to_canonical[lbl] or lbl or ""
            consolidated_nodes.append(rep_node)

    # Re-route edges and consolidate weights
    consolidated_edges_map = {}
    for e in edges:
        src = id_to_canonical_id.get(e["from"], e["from"])
        dst = id_to_canonical_id.get(e["to"], e["to"])
        rel_label = e.get("label") or ""

        # Omit self-loops created by node merging
        if src == dst:
            continue

        edge_key = (src, dst, rel_label)
        weight = e.get("weight", 1)

        if edge_key not in consolidated_edges_map:
            consolidated_edges_map[edge_key] = {
                "from": src,
                "to": dst,
                "label": rel_label,
                "weight": weight
            }
        else:
            consolidated_edges_map[edge_key]["weight"] += weight

    consolidated_edges = list(consolidated_edges_map.values())
    return consolidated_nodes, consolidated_edges

