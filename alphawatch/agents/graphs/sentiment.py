"""SentimentGraph — LangGraph workflow for news ingestion and sentiment scoring.

Pipeline: fetch_news → parse_articles → store_articles →
          score_sentiments → store_sentiments → handle_errors → END

If fetch_news returns no articles, the graph skips directly
to handle_errors and exits.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from alphawatch.agents.nodes.sentiment import (
    fetch_news,
    handle_errors,
    parse_articles,
    score_sentiments,
    store_articles,
    store_sentiments,
)
from alphawatch.agents.state import SentimentState


def _has_articles(state: SentimentState) -> str:
    """Route after fetch_news: continue if articles found, else end.

    Args:
        state: Current sentiment state.

    Returns:
        Next node name: 'parse_articles' or 'handle_errors'.
    """
    articles = state.get("articles", [])
    return "parse_articles" if articles else "handle_errors"


def build_sentiment_graph() -> CompiledStateGraph:
    """Build and compile the SentimentGraph.

    Returns:
        A compiled LangGraph graph ready for invocation.
    """
    graph = StateGraph(SentimentState)

    # Add nodes
    graph.add_node("fetch_news", fetch_news)
    graph.add_node("parse_articles", parse_articles)
    graph.add_node("store_articles", store_articles)
    graph.add_node("score_sentiments", score_sentiments)
    graph.add_node("store_sentiments", store_sentiments)
    graph.add_node("handle_errors", handle_errors)

    # Entry point
    graph.set_entry_point("fetch_news")

    # Conditional edge: skip pipeline if no articles found
    graph.add_conditional_edges(
        "fetch_news",
        _has_articles,
        {
            "parse_articles": "parse_articles",
            "handle_errors": "handle_errors",
        },
    )

    # Linear pipeline
    graph.add_edge("parse_articles", "store_articles")
    graph.add_edge("store_articles", "score_sentiments")
    graph.add_edge("score_sentiments", "store_sentiments")
    graph.add_edge("store_sentiments", "handle_errors")

    # Terminal
    graph.add_edge("handle_errors", END)

    return graph.compile()
