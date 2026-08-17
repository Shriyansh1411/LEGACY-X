from __future__ import annotations
from typing import Dict, Any, List
import networkx as nx

from app.parsers.cobol_parser import parse_cobol


def build_dependency_graph(file_contents: Dict[str, str], source_files: List[str]) -> Dict[str, Any]:
    """Build a lightweight dependency graph from parsed COBOL files.

    Returns a serializable dict with `nodes` and `edges` and a list of
    `high_risk_modules` flagged by degree and IO intensity.
    """
    G = nx.DiGraph()

    # Map paragraph name -> (file, paragraph_id)
    para_index: Dict[str, Dict[str, str]] = {}

    # Create file and paragraph nodes
    for f in source_files:
        text = file_contents.get(f, "")
        if not text:
            continue
        parsed = parse_cobol(text)
        file_node = f
        G.add_node(file_node, type="file", file=f)

        for p in parsed.get("paragraphs", []):
            pid = f + "::" + p
            G.add_node(pid, type="paragraph", label=p, file=f)
            G.add_edge(file_node, pid)
            para_index[p.upper()] = {"file": f, "id": pid}

    # Add perform edges
    for f in source_files:
        text = file_contents.get(f, "")
        if not text:
            continue
        parsed = parse_cobol(text)
        for src_para in parsed.get("paragraphs", []):
            src_id = f + "::" + src_para
            for callee in parsed.get("performs", []):
                key = callee.upper()
                target = para_index.get(key)
                if target:
                    G.add_edge(src_id, target["id"], type="perform")
                else:
                    # unknown target: attach to file node as external dependency
                    G.add_edge(src_id, f + "::" + callee)

        # mark IO intensity as attribute
        io_ops = parsed.get("io_ops", [])
        if io_ops:
            G.nodes[f]["io_ops"] = len(io_ops)
        else:
            G.nodes[f]["io_ops"] = 0

    # Compute high-risk modules: files with high degree or high IO ops
    nodes_info = []
    for n, attr in G.nodes(data=True):
        deg = G.degree(n)
        nodes_info.append({"id": n, "attrs": attr, "degree": deg})

    high_risk = []
    for info in nodes_info:
        nid = info["id"]
        attrs = info["attrs"]
        deg = info["degree"]
        # file-level risk: degree >=3 or io_ops >=3
        if attrs.get("type") == "file" and (deg >= 3 or attrs.get("io_ops", 0) >= 3):
            high_risk.append(nid)

    # Serialize edges
    edges = []
    for a, b, d in G.edges(data=True):
        edges.append({"source": a, "target": b, "attrs": d})

    return {
        "nodes": nodes_info,
        "edges": edges,
        "high_risk_modules": sorted(high_risk),
    }
