"""BriefGraph — LangGraph workflow for analyst brief generation.

Pipeline
--------
retrieve_chunks
    └─ fan-out via Send (parallel)
        ├─ build_snapshot
        ├─ build_what_changed
        ├─ build_risk_flags
        ├─ build_sentiment
        └─ build_sources
    └─ assemble_sections  (fan-in)
        └─ build_executive_summary
            └─ build_suggested_followups
                └─ store_brief
                    └─ handle_errors → END

The five section-builder nodes run in parallel after retrieve_chunks via
LangGraph's Send API.  assemble_sections collects their outputs before the
sequential executive-summary step begins, ensuring the summary can only
reference information that was surfaced in earlier sections.
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from alphawatch.agents.nodes.brief import (
    assemble_sections,
    build_executive_summary,
    build_risk_flags,
    build_sentiment,
    build_snapshot,
    build_sources,
    build_suggested_followups,
    build_what_changed,
    handle_errors,
    retrieve_chunks,
    store_brief,
)
from alphawatch.agents.state import BriefState

# ---------------------------------------------------------------------------
# Fan-out routing
# ---------------------------------------------------------------------------


def _fan_out_sections(state: BriefState) -> list[Send]:
    """Route from retrieve_chunks to all five parallel section builders.

    Each Send carries the full current state so every section builder has
    access to retrieved_chunks, ticker, company_id, etc.

    Args:
        state: Current brief state after retrieve_chunks has run.

    Returns:
        List of Send objects targeting each parallel section-builder node.
    """
    # Cast to dict so Send can forward it as a state patch
    state_snapshot: dict[str, Any] = dict(state)
    return [
        Send("build_snapshot", state_snapshot),
        Send("build_what_changed", state_snapshot),
        Send("build_risk_flags", state_snapshot),
        Send("build_sentiment", state_snapshot),
        Send("build_sources", state_snapshot),
    ]


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_brief_graph() -> CompiledStateGraph:
    """Build and compile the BriefGraph.

    The graph implements a fan-out / fan-in pattern:

    1. ``retrieve_chunks`` embeds a broad company query and pulls the top-8
       most similar EDGAR chunks from pgvector.
    2. Five section builders run **in parallel** via ``Send``:
       - ``build_snapshot``      — latest financial metrics (data-driven)
       - ``build_what_changed``  — snapshot diff (data-driven, no LLM)
       - ``build_risk_flags``    — LLM-identified risks from chunks
       - ``build_sentiment``     — pre-computed sentiment aggregates
       - ``build_sources``       — deduplicated citation list (data-driven)
    3. ``assemble_sections`` fans-in all parallel outputs into an ordered list.
    4. ``build_executive_summary`` synthesises the sections (LLM, runs last).
    5. ``build_suggested_followups`` generates chat follow-up chips (LLM, Haiku).
    6. ``store_brief`` persists the brief and all sections to PostgreSQL.
    7. ``handle_errors`` logs any accumulated errors and terminates.

    Returns:
        A compiled LangGraph graph ready for ``ainvoke``.
    """
    graph = StateGraph(BriefState)

    # --- Nodes ---
    graph.add_node("retrieve_chunks", retrieve_chunks)
    graph.add_node("build_snapshot", build_snapshot)
    graph.add_node("build_what_changed", build_what_changed)
    graph.add_node("build_risk_flags", build_risk_flags)
    graph.add_node("build_sentiment", build_sentiment)
    graph.add_node("build_sources", build_sources)
    graph.add_node("assemble_sections", assemble_sections)
    graph.add_node("build_executive_summary", build_executive_summary)
    graph.add_node("build_suggested_followups", build_suggested_followups)
    graph.add_node("store_brief", store_brief)
    graph.add_node("handle_errors", handle_errors)

    # --- Entry point ---
    graph.set_entry_point("retrieve_chunks")

    # --- Fan-out: retrieve_chunks → 5 parallel section builders via Send ---
    graph.add_conditional_edges(
        "retrieve_chunks",
        _fan_out_sections,
        [
            "build_snapshot",
            "build_what_changed",
            "build_risk_flags",
            "build_sentiment",
            "build_sources",
        ],
    )

    # --- Fan-in: all section builders → assemble_sections ---
    graph.add_edge("build_snapshot", "assemble_sections")
    graph.add_edge("build_what_changed", "assemble_sections")
    graph.add_edge("build_risk_flags", "assemble_sections")
    graph.add_edge("build_sentiment", "assemble_sections")
    graph.add_edge("build_sources", "assemble_sections")

    # --- Sequential tail ---
    graph.add_edge("assemble_sections", "build_executive_summary")
    graph.add_edge("build_executive_summary", "build_suggested_followups")
    graph.add_edge("build_suggested_followups", "store_brief")
    graph.add_edge("store_brief", "handle_errors")

    # --- Terminal ---
    graph.add_edge("handle_errors", END)

    return graph.compile()
