"""API routes for behavior graph analysis."""

from fastapi import APIRouter, HTTPException
from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.behavior_graph import BehaviorGraphResponse

router = APIRouter(prefix="/api/projects", tags=["behavior-graph"])


@router.get("/{project_id}/behavior-graph", response_model=BehaviorGraphResponse)
def get_behavior_graph(project_id: str) -> BehaviorGraphResponse:
    """
    Get the behavior graph for a project.
    
    The behavior graph is built during the understand stage and shows:
    - Key behavioral nodes (decisions, operations, variables)
    - Relationships between behaviors
    - Confidence scores and risk levels
    - Critical execution paths
    
    Args:
        project_id: Project identifier
        
    Returns:
        BehaviorGraphResponse with complete behavior graph data
        
    Raises:
        HTTPException: If project not found or behavior graph not available
    """
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if not project.behavior_graph:
            raise HTTPException(
                status_code=404,
                detail="Behavior graph not available. Ensure understand stage has completed.",
            )
    
    return BehaviorGraphResponse(
        project_id=project_id,
        behavior_graph=project.behavior_graph,
    )


@router.get("/{project_id}/behavior-graph/summary")
def get_behavior_graph_summary(project_id: str) -> dict:
    """
    Get a summary of the behavior graph (stats only).
    
    Args:
        project_id: Project identifier
        
    Returns:
        Dictionary with behavior graph statistics
        
    Raises:
        HTTPException: If project not found or behavior graph not available
    """
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if not project.behavior_graph:
            raise HTTPException(
                status_code=404,
                detail="Behavior graph not available. Ensure understand stage has completed.",
            )
    
    graph_data = project.behavior_graph
    return {
        "project_id": project_id,
        "stats": graph_data.get("stats", {}),
        "entry_points": graph_data.get("entry_points", []),
        "exit_points": graph_data.get("exit_points", []),
        "critical_paths_count": len(graph_data.get("critical_paths", [])),
    }


@router.get("/{project_id}/behavior-graph/risks")
def get_behavior_graph_risks(project_id: str) -> dict:
    """
    Get high-risk nodes and paths from the behavior graph.
    
    Args:
        project_id: Project identifier
        
    Returns:
        Dictionary with high-risk nodes and low-confidence nodes
        
    Raises:
        HTTPException: If project not found or behavior graph not available
    """
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if not project.behavior_graph:
            raise HTTPException(
                status_code=404,
                detail="Behavior graph not available. Ensure understand stage has completed.",
            )
    
    graph_data = project.behavior_graph
    nodes = graph_data.get("nodes", [])
    
    high_risk_nodes = [
        node for node in nodes if node.get("risk_level") == "high"
    ]
    low_confidence_nodes = [
        node for node in nodes if node.get("confidence", 0) < 0.6
    ]
    
    return {
        "project_id": project_id,
        "high_risk_nodes": high_risk_nodes,
        "low_confidence_nodes": low_confidence_nodes,
        "total_high_risk": len(high_risk_nodes),
        "total_low_confidence": len(low_confidence_nodes),
        "recommendation": (
            "Focus code generation on high-risk and low-confidence nodes to ensure quality."
            if high_risk_nodes or low_confidence_nodes
            else "Behavior graph is stable with acceptable confidence levels."
        ),
    }
