"""IngestionGraph — LangGraph workflow for SEC EDGAR ingestion.

Pipeline: fetch_filings → parse_documents → chunk_documents →
          embed_chunks → store_chunks → handle_errors → END

If fetch_filings returns no new filings, the graph skips directly
to handle_errors and exits.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from alphawatch.agents.nodes.ingestion import (
    chunk_documents,
    embed_chunks,
    fetch_filings,
    handle_errors,
    parse_documents,
    store_chunks,
)
from alphawatch.agents.state import IngestionState


def _has_new_filings(state: IngestionState) -> str:
    """Route after fetch_filings: continue if filings found, else end.

    Args:
        state: Current ingestion state.

    Returns:
        Next node name: 'parse_documents' or 'handle_errors'.
    """
    filings = state.get("new_filings", [])
    return "parse_documents" if filings else "handle_errors"


def build_ingestion_graph() -> CompiledStateGraph:
    """Build and compile the IngestionGraph.

    Returns:
        A compiled LangGraph graph ready for invocation.
    """
    graph = StateGraph(IngestionState)

    # Add nodes
    graph.add_node("fetch_filings", fetch_filings)
    graph.add_node("parse_documents", parse_documents)
    graph.add_node("chunk_documents", chunk_documents)
    graph.add_node("embed_chunks", embed_chunks)
    graph.add_node("store_chunks", store_chunks)
    graph.add_node("handle_errors", handle_errors)

    # Entry point
    graph.set_entry_point("fetch_filings")

    # Conditional edge: skip pipeline if no new filings
    graph.add_conditional_edges(
        "fetch_filings",
        _has_new_filings,
        {
            "parse_documents": "parse_documents",
            "handle_errors": "handle_errors",
        },
    )

    # Linear pipeline
    graph.add_edge("parse_documents", "chunk_documents")
    graph.add_edge("chunk_documents", "embed_chunks")
    graph.add_edge("embed_chunks", "store_chunks")
    graph.add_edge("store_chunks", "handle_errors")

    # Terminal
    graph.add_edge("handle_errors", END)

    return graph.compile()
