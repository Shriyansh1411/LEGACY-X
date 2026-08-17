"""
Behavior Graph Service - Builds a unified behavior graph from analysis and understanding.

The behavior graph captures:
- Key behavioral nodes (decisions, operations, transitions)
- Relationships and dependencies between behaviors
- Confidence scores and risk levels
- Execution paths and edge cases
"""

import re
from typing import Dict, Any, List
import networkx as nx
from app.schemas.analysis import LegacyAnalysis
from app.schemas.blueprint import BehavioralBlueprint


class BehaviorNode:
    """Represents a behavioral node in the graph."""
    
    def __init__(
        self,
        node_id: str,
        node_type: str,  # 'decision', 'operation', 'branch', 'io', 'variable'
        label: str,
        confidence: float = 0.5,
        source_file: str | None = None,
        line_hint: str | None = None,
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.label = label
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
        self.source_file = source_file
        self.line_hint = line_hint
        self.risk_level = self._calculate_risk_level()

    def _calculate_risk_level(self) -> str:
        """Calculate risk level based on confidence and type."""
        if self.node_type == 'decision':
            if self.confidence < 0.6:
                return 'high'
            elif self.confidence < 0.8:
                return 'medium'
            return 'low'
        elif self.node_type == 'io':
            return 'high' if self.confidence < 0.8 else 'medium'
        return 'low'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.node_id,
            'type': self.node_type,
            'label': self.label,
            'confidence': self.confidence,
            'risk_level': self.risk_level,
            'source_file': self.source_file,
            'line_hint': self.line_hint,
        }


class BehaviorEdge:
    """Represents a relationship between behavioral nodes."""
    
    def __init__(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,  # 'depends_on', 'triggers', 'branches_to', 'calls'
        label: str | None = None,
        condition: str | None = None,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.edge_type = edge_type
        self.label = label or edge_type
        self.condition = condition

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source': self.source_id,
            'target': self.target_id,
            'type': self.edge_type,
            'label': self.label,
            'condition': self.condition,
        }


class BehaviorGraph:
    """Builds and manages a unified behavior graph from analysis and blueprint."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes_by_id: Dict[str, BehaviorNode] = {}
        self.edges: List[BehaviorEdge] = []
        self.entry_points: List[str] = []
        self.exit_points: List[str] = []
        self.critical_paths: List[List[str]] = []

    def add_node(self, node: BehaviorNode) -> None:
        """Add a behavior node to the graph."""
        self.nodes_by_id[node.node_id] = node
        self.graph.add_node(
            node.node_id,
            type=node.node_type,
            label=node.label,
            confidence=node.confidence,
            risk_level=node.risk_level,
        )

    def add_edge(self, edge: BehaviorEdge) -> None:
        """Add a relationship edge between nodes."""
        self.edges.append(edge)
        self.graph.add_edge(
            edge.source_id,
            edge.target_id,
            type=edge.edge_type,
            label=edge.label,
            condition=edge.condition,
        )

    def _extract_decisions_from_signals(self, signals: List[str]) -> List[BehaviorNode]:
        """Extract decision nodes from actual legacy control-flow signals."""
        normalized: List[str] = []
        seen = set()
        for signal in signals or []:
            if not isinstance(signal, str):
                continue
            clean = signal.strip()
            if not clean or clean.upper() in seen:
                continue
            seen.add(clean.upper())
            normalized.append(clean)

        nodes = []
        signal_to_type = {
            'IF': 'decision',
            'PERFORM': 'operation',
            'MOVE': 'operation',
            'IO': 'io',
            'READ': 'io',
            'WRITE': 'io',
            'DISPLAY': 'io',
        }

        for idx, sig in enumerate(normalized[:6]):
            key = sig.upper()
            node_type = signal_to_type.get(key, 'operation')
            label = sig
            if key == 'IF':
                label = 'IF condition'
            elif key == 'MOVE':
                label = 'MOVE assignment'
            elif key == 'IO':
                label = 'I/O operation'
            elif key == 'PERFORM':
                label = 'PERFORM call'
            elif key == 'DISPLAY':
                label = 'DISPLAY output'
            node = BehaviorNode(
                node_id=f'signal_{idx}_{key.lower()}',
                node_type=node_type,
                label=label,
                confidence=0.75,
                line_hint=f'Control flow signal: {sig}',
            )
            nodes.append(node)

        return nodes

    def _extract_nodes_from_rules(self, rules: List[Dict[str, Any]]) -> List[BehaviorNode]:
        """Extract behavior nodes from blueprint rules."""
        nodes = []
        
        for i, rule_entry in enumerate(rules):
            if isinstance(rule_entry, dict):
                rule_text = rule_entry.get('rule', str(rule_entry))
                confidence = float(rule_entry.get('confidence', 0.5))
                source_evidence = rule_entry.get('source_evidence', {})
                depends_on = rule_entry.get('depends_on', [])
            else:
                rule_text = str(rule_entry)
                confidence = 0.5
                source_evidence = {}
                depends_on = []

            node = BehaviorNode(
                node_id=f'rule_{i}_{rule_text[:20].lower().replace(" ", "_")}',
                node_type='decision',
                label=rule_text[:50],
                confidence=confidence,
                source_file=source_evidence.get('file') if isinstance(source_evidence, dict) else None,
                line_hint=source_evidence.get('line_hint') if isinstance(source_evidence, dict) else None,
            )
            nodes.append(node)
        
        return nodes

    def _extract_nodes_from_dependencies(self, dependencies: List[str]) -> List[BehaviorNode]:
        """Extract variable/dependency nodes."""
        nodes = []
        
        for dep in set(dependencies):
            node = BehaviorNode(
                node_id=f'var_{dep.lower()}',
                node_type='variable',
                label=f'Variable: {dep}',
                confidence=0.8,
                line_hint=f'Dependency: {dep}',
            )
            nodes.append(node)
        
        return nodes

    def build_from_analysis_and_blueprint(
        self,
        analysis: LegacyAnalysis,
        blueprint: BehavioralBlueprint,
    ) -> None:
        """Build behavior graph from analysis and blueprint data."""

        signal_nodes = self._extract_decisions_from_signals(
            analysis.control_flow_signals or []
        )
        if not signal_nodes and blueprint.rules:
            rule_signals = []
            for rule in blueprint.rules:
                matches = re.findall(r"\b(IF|WHEN|MOVE|SET|CHECK|DISPLAY|READ|WRITE|REVIEW|STATUS|TOTAL)\b", str(rule).upper())
                rule_signals.extend(matches)
            signal_nodes = self._extract_decisions_from_signals(rule_signals)

        for node in signal_nodes:
            self.add_node(node)

        rule_nodes = self._extract_nodes_from_rules(blueprint.rules or [])
        for node in rule_nodes:
            self.add_node(node)
        self.entry_points = [node.node_id for node in rule_nodes[:1]]

        dep_nodes = self._extract_nodes_from_dependencies(blueprint.dependencies or [])
        for node in dep_nodes:
            self.add_node(node)

        # Add edges: rules depend on variables
        for rule_node in rule_nodes:
            for dep_node in dep_nodes:
                edge = BehaviorEdge(
                    source_id=dep_node.node_id,
                    target_id=rule_node.node_id,
                    edge_type='depends_on',
                    label=f'{dep_node.label} → {rule_node.label}',
                )
                self.add_edge(edge)

        # Add edges: signals trigger rules
        if signal_nodes and rule_nodes:
            for sig_node in signal_nodes:
                for rule_node in rule_nodes:
                    edge = BehaviorEdge(
                        source_id=sig_node.node_id,
                        target_id=rule_node.node_id,
                        edge_type='triggers',
                        label=f'{sig_node.label} triggers {rule_node.label}',
                    )
                    self.add_edge(edge)

        # Identify exit points (nodes with no outgoing edges except exit)
        self.exit_points = [
            nid for nid in self.graph.nodes()
            if self.graph.out_degree(nid) == 0 and nid not in self.entry_points
        ]

        # Extract critical paths (high-confidence paths from entry to exit)
        self._extract_critical_paths()

    def _extract_critical_paths(self) -> None:
        """Extract critical execution paths with high confidence."""
        if not self.entry_points or not self.exit_points:
            return

        paths = []
        for start in self.entry_points:
            for end in self.exit_points:
                try:
                    simple_paths = list(nx.all_simple_paths(self.graph, start, end))
                    for path in simple_paths:
                        # Calculate path confidence as average of node confidences
                        confidences = [
                            self.nodes_by_id.get(node_id, BehaviorNode('', '', '')).confidence
                            for node_id in path
                        ]
                        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                        if avg_confidence >= 0.7:  # Only include high-confidence paths
                            paths.append({
                                'path': path,
                                'confidence': avg_confidence,
                            })
                except nx.NetworkXNoPath:
                    pass

        # Sort by confidence (descending) and keep top 5
        self.critical_paths = [
            p['path'] for p in sorted(paths, key=lambda x: x['confidence'], reverse=True)[:5]
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the behavior graph to a dictionary."""
        return {
            'nodes': [node.to_dict() for node in self.nodes_by_id.values()],
            'edges': [edge.to_dict() for edge in self.edges],
            'entry_points': self.entry_points,
            'exit_points': self.exit_points,
            'critical_paths': self.critical_paths,
            'stats': {
                'total_nodes': len(self.nodes_by_id),
                'total_edges': len(self.edges),
                'high_risk_nodes': sum(
                    1 for node in self.nodes_by_id.values()
                    if node.risk_level == 'high'
                ),
                'avg_confidence': (
                    sum(node.confidence for node in self.nodes_by_id.values()) /
                    len(self.nodes_by_id) if self.nodes_by_id else 0.0
                ),
            },
        }


def build_behavior_graph(
    analysis: LegacyAnalysis,
    blueprint: BehavioralBlueprint,
) -> Dict[str, Any]:
    """
    Build a behavior graph from analysis and blueprint data.
    
    Args:
        analysis: Legacy code analysis with signals and rules
        blueprint: Behavioral blueprint with rules and dependencies
        
    Returns:
        Serialized behavior graph with nodes, edges, paths, and statistics
    """
    graph = BehaviorGraph()
    graph.build_from_analysis_and_blueprint(analysis, blueprint)
    result = graph.to_dict()

    if not (analysis.control_flow_signals or []):
        rule_text = "; ".join(str(rule) for rule in (blueprint.rules or [])[:3])
        dependency_text = ", ".join(str(dep) for dep in (blueprint.dependencies or [])[:5])
        if rule_text:
            result['summary'] = (
                "No explicit control-flow signals were detected in the legacy source. "
                "The model inferred the behavior as: " + rule_text +
                (f". Dependencies: {dependency_text}." if dependency_text else ".")
            )
        else:
            result['summary'] = "No explicit control-flow signals were detected in the legacy source; the understand stage captured the behavioral intent without clear branching patterns."
    else:
        result['summary'] = "Behavior graph derived from legacy control-flow and blueprint rules."

    return result
