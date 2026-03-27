"""ChatGraph — LangGraph workflow for multi-turn RAG chat.

Pipeline
--------
prepare_context
    └─ detect_intent
        ├─ (rag / comparison) → check_chunk_cache
        │       ├─ (cache miss)  → retrieve_chunks → generate_response
        │       └─ (cache hit)   → generate_response
        └─ (general)            → generate_response
    └─ generate_response
        └─ generate_followups
            └─ persist_turn
                └─ maybe_summarize
                    └─ handle_errors → END

Conditional routing
-------------------
- ``_route_by_intent``: after detect_intent, routes to check_chunk_cache
  (rag/comparison) or directly to generate_response (general).
- ``_route_by_cache``: after check_chunk_cache, routes to retrieve_chunks
  (cache miss) or directly to generate_response (cache hit).

The graph always terminates at handle_errors → END, even on partial
failure, because every node catches exceptions and appends to state.errors
rather than raising.
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from alphawatch.agents.nodes.chat import (
    check_chunk_cache,
    detect_intent,
    generate_followups,
    generate_response,
    handle_errors,
    maybe_summarize,
    persist_turn,
    prepare_context,
    retrieve_chunks,
)
from alphawatch.agents.state import ChatState

# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def _route_by_intent(state: ChatState) -> str:
    """Route after detect_intent based on classified intent.

    Args:
        state: Current chat state with intent set by detect_intent.

    Returns:
        Next node name: 'check_chunk_cache' for rag/comparison,
        'generate_response' for general questions.
    """
    intent = state.get("intent", "rag")
    if intent in {"rag", "comparison"}:
        return "check_chunk_cache"
    return "generate_response"


def _route_by_cache(state: ChatState) -> str:
    """Route after check_chunk_cache based on whether chunks were served.

    Args:
        state: Current chat state with cache_hit flag set by check_chunk_cache.

    Returns:
        Next node name: 'retrieve_chunks' on cache miss,
        'generate_response' on cache hit.
    """
    if state.get("cache_hit", False):
        return "generate_response"
    return "retrieve_chunks"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_chat_graph() -> CompiledStateGraph:
    """Build and compile the ChatGraph.

    The graph implements a single-turn RAG chat pipeline with:

    1. ``prepare_context`` — loads the session from PostgreSQL and builds
       the LLM context window (rolling summary + last 10 messages).
    2. ``detect_intent`` — classifies the user message as 'rag',
       'comparison', or 'general' using Claude Haiku. Extracts a
       comparison ticker if present.
    3. ``check_chunk_cache`` — loads previously retrieved chunks from
       the session cache by UUID. Sets ``cache_hit=True`` if chunks
       were found.  Skipped entirely for 'general' intent.
    4. ``retrieve_chunks`` — embeds the user query via Titan Embeddings v2
       and runs pgvector cosine similarity search. Only runs on cache miss.
    5. ``generate_response`` — calls Claude Sonnet with the context window,
       source chunks, and user question. Returns the response text and
       citations.
    6. ``generate_followups`` — calls Claude Haiku to produce 3 follow-up
       question chips.
    7. ``persist_turn`` — appends user + assistant messages to the session
       and merges new chunk IDs into the chunk cache.
    8. ``maybe_summarize`` — if the session has exceeded 20 messages,
       summarises older messages via Claude Haiku and persists the rolling
       context summary.
    9. ``handle_errors`` — logs accumulated errors (terminal node).

    Returns:
        A compiled LangGraph graph ready for ``ainvoke`` or ``astream``.
    """
    graph = StateGraph(ChatState)

    # --- Nodes ---
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("check_chunk_cache", check_chunk_cache)
    graph.add_node("retrieve_chunks", retrieve_chunks)
    graph.add_node("generate_response", generate_response)
    graph.add_node("generate_followups", generate_followups)
    graph.add_node("persist_turn", persist_turn)
    graph.add_node("maybe_summarize", maybe_summarize)
    graph.add_node("handle_errors", handle_errors)

    # --- Entry point ---
    graph.set_entry_point("prepare_context")

    # --- prepare_context → detect_intent (always) ---
    graph.add_edge("prepare_context", "detect_intent")

    # --- detect_intent → check_chunk_cache | generate_response ---
    graph.add_conditional_edges(
        "detect_intent",
        _route_by_intent,
        {
            "check_chunk_cache": "check_chunk_cache",
            "generate_response": "generate_response",
        },
    )

    # --- check_chunk_cache → retrieve_chunks | generate_response ---
    graph.add_conditional_edges(
        "check_chunk_cache",
        _route_by_cache,
        {
            "retrieve_chunks": "retrieve_chunks",
            "generate_response": "generate_response",
        },
    )

    # --- retrieve_chunks → generate_response (always) ---
    graph.add_edge("retrieve_chunks", "generate_response")

    # --- Sequential tail ---
    graph.add_edge("generate_response", "generate_followups")
    graph.add_edge("generate_followups", "persist_turn")
    graph.add_edge("persist_turn", "maybe_summarize")
    graph.add_edge("maybe_summarize", "handle_errors")

    # --- Terminal ---
    graph.add_edge("handle_errors", END)

    return graph.compile()
