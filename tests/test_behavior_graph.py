#!/usr/bin/env python3
"""Test script to verify behavior graph building and API endpoints."""

import requests
import json
import time

API_BASE = "http://localhost:8012/api"

def test_behavior_graph_pipeline():
    """Test the complete pipeline with behavior graph building."""
    
    print("\n=== TESTING BEHAVIOR GRAPH PIPELINE ===\n")
    
    # Step 1: Create project
    print("1. Creating project...")
    project_data = {
        "project_id": "test_behavior_graph_001",
        "file_count": 1,
        "source_files": ["source.cbl"],
        "docs": [],
        "logs": [],
        "language_hint": "cobol",
        "file_contents": {
            "source.cbl": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEGACY-TOTAL-CHECK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 TOTAL PIC 9(5) VALUE 0.
       01 STATUS PIC X(4) VALUE 'LOW'.
       PROCEDURE DIVISION.
           MOVE 150 TO TOTAL.
           IF TOTAL > 100 THEN
               MOVE 'HIGH' TO STATUS
           ELSE
               MOVE 'LOW' TO STATUS
           END-IF.
           STOP RUN."""
        }
    }
    
    response = requests.post(f"{API_BASE}/projects", json=project_data)
    if response.status_code != 200:
        print(f"Failed to create project: {response.text}")
        return
    project = response.json()
    project_id = project.get("project_id")
    print(f"✓ Project created: {project_id}")
    
    # Step 2: Run ingest
    print("\n2. Running ingest stage...")
    response = requests.post(f"{API_BASE}/projects/{project_id}/ingest")
    if response.status_code == 200:
        print("✓ Ingest completed")
    
    # Step 3: Run analyze
    print("\n3. Running analyze stage...")
    response = requests.post(f"{API_BASE}/projects/{project_id}/analyze")
    if response.status_code == 200:
        analysis = response.json()
        signals = analysis.get("analysis", {}).get("control_flow_signals", [])
        print(f"✓ Analyze completed, signals: {signals}")
    
    # Step 4: Run understand (this builds the behavior graph)
    print("\n4. Running understand stage (builds behavior graph)...")
    response = requests.post(f"{API_BASE}/projects/{project_id}/understand")
    if response.status_code == 200:
        blueprint = response.json()
        rules = blueprint.get("blueprint", {}).get("rules", [])
        print(f"✓ Understand completed, extracted {len(rules)} rules")
    
    # Step 5: Get behavior graph
    print("\n5. Retrieving behavior graph...")
    response = requests.get(f"{API_BASE}/projects/{project_id}/behavior-graph")
    if response.status_code == 200:
        bg_response = response.json()
        behavior_graph = bg_response.get("behavior_graph", {})
        nodes = behavior_graph.get("nodes", [])
        edges = behavior_graph.get("edges", [])
        stats = behavior_graph.get("stats", {})
        print(f"✓ Behavior graph retrieved:")
        print(f"   - Nodes: {len(nodes)}")
        print(f"   - Edges: {len(edges)}")
        print(f"   - Entry points: {behavior_graph.get('entry_points', [])}")
        print(f"   - Stats: {stats}")
        
        if nodes:
            print(f"\n   Sample nodes:")
            for node in nodes[:3]:
                print(f"   - {node.get('label')} (type: {node.get('type')}, confidence: {node.get('confidence')})")
    else:
        print(f"✗ Failed to get behavior graph: {response.status_code}")
        print(response.text)
        return
    
    # Step 6: Get behavior graph summary
    print("\n6. Retrieving behavior graph summary...")
    response = requests.get(f"{API_BASE}/projects/{project_id}/behavior-graph/summary")
    if response.status_code == 200:
        summary = response.json()
        print(f"✓ Summary retrieved:")
        print(f"   - Stats: {summary.get('stats', {})}")
        print(f"   - Critical paths: {summary.get('critical_paths_count', 0)}")
    
    # Step 7: Get behavior graph risks
    print("\n7. Retrieving behavior graph risks...")
    response = requests.get(f"{API_BASE}/projects/{project_id}/behavior-graph/risks")
    if response.status_code == 200:
        risks = response.json()
        print(f"✓ Risks retrieved:")
        print(f"   - High-risk nodes: {risks.get('total_high_risk', 0)}")
        print(f"   - Low-confidence nodes: {risks.get('total_low_confidence', 0)}")
        print(f"   - Recommendation: {risks.get('recommendation', '')}")
    
    # Step 8: Run generate (will use behavior graph)
    print("\n8. Running generate stage (uses behavior graph)...")
    response = requests.post(f"{API_BASE}/projects/{project_id}/generate")
    if response.status_code == 200:
        gen_result = response.json()
        code = gen_result.get("generated_code", "")
        print(f"✓ Generate completed, generated {len(code)} chars")
    
    print("\n=== BEHAVIOR GRAPH PIPELINE TEST COMPLETE ===\n")


if __name__ == "__main__":
    test_behavior_graph_pipeline()
