"""Behavior Graph schemas."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class BehaviorNodeSchema(BaseModel):
    """A node in the behavior graph."""
    id: str
    type: str  # 'decision', 'operation', 'branch', 'io', 'variable'
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: str  # 'low', 'medium', 'high'
    source_file: Optional[str] = None
    line_hint: Optional[str] = None


class BehaviorEdgeSchema(BaseModel):
    """An edge representing a relationship between behavior nodes."""
    source: str
    target: str
    type: str  # 'depends_on', 'triggers', 'branches_to', 'calls'
    label: str
    condition: Optional[str] = None


class BehaviorGraphStatsSchema(BaseModel):
    """Statistics about the behavior graph."""
    total_nodes: int
    total_edges: int
    high_risk_nodes: int
    avg_confidence: float = Field(ge=0.0, le=1.0)


class BehaviorGraphSchema(BaseModel):
    """Complete behavior graph extracted from code analysis and blueprint."""
    nodes: List[BehaviorNodeSchema]
    edges: List[BehaviorEdgeSchema]
    entry_points: List[str] = Field(description="Entry points to the behavior graph")
    exit_points: List[str] = Field(description="Exit points from the behavior graph")
    critical_paths: List[List[str]] = Field(description="High-confidence execution paths")
    stats: BehaviorGraphStatsSchema


class BehaviorGraphResponse(BaseModel):
    """API response with behavior graph."""
    project_id: str
    behavior_graph: BehaviorGraphSchema
