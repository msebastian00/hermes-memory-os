"""Optional, evidence-backed Neo4j graph layer for Hermes Memory OS."""

from .builder import GraphBookBuilder
from .flags import graph_enabled
from .retrieval import GraphRetrievalAdapter
from .tools import dispatch_graph_tool

__all__ = [
    "GraphBookBuilder",
    "GraphRetrievalAdapter",
    "dispatch_graph_tool",
    "graph_enabled",
]
