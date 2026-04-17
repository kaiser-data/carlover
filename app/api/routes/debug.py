from fastapi import APIRouter, Request

from app.schemas.responses import GraphDebugResponse

router = APIRouter()


@router.get("/debug/graph", response_model=GraphDebugResponse, tags=["debug"])
async def debug_graph(request: Request) -> GraphDebugResponse:
    """
    Return the LangGraph structure as a JSON-serializable dict.
    Useful for visualizing the agent workflow.
    """
    graph = request.app.state.graph
    graph_data = graph.get_graph()

    nodes = [node for node in graph_data.nodes]
    edges = [
        {"source": e.source, "target": e.target}
        for e in graph_data.edges
    ]

    return GraphDebugResponse(
        nodes=nodes,
        edges=edges,
        entry_point="intake",
    )
