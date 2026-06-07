"""Hermes MemoryProvider adapter.

The exact Hermes provider base class can vary by deployment. This adapter keeps the
behavior isolated behind plain Python methods so it can be wrapped by the installed
Hermes plugin interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hermes_memory_os.app import MemoryApp


class HermesMemoryOSProvider:
    """Provider-style interface for Hermes."""

    def __init__(self) -> None:
        self.app: MemoryApp | None = None

    def initialize(self, config: dict[str, Any] | str | Path | None = None, hermes_home: str | Path | None = None) -> None:
        config_path = config if isinstance(config, (str, Path)) else None
        data_dir = None
        if isinstance(config, dict):
            data_dir = config.get("data_dir")
            config_path = config.get("config_path")
        self.app = MemoryApp.from_config(config_path=config_path, data_dir=data_dir)
        self.app.init_storage()

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "hermes_memory_search",
                "description": "Search local Hermes durable memory and indexed wiki-brain content.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "scope": {"type": "string"},
                        "memory_type": {"type": "string"},
                        "source_types": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "default": 8},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hermes_memory_add",
                "description": "Add an explicit durable memory.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "memory_type": {"type": "string"},
                        "scope": {"type": "string"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "canonical_text": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "entities": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["memory_type", "scope", "summary", "canonical_text"],
                },
            },
            {
                "name": "hermes_memory_archive",
                "description": "Archive a memory without deleting raw history.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["memory_id"],
                },
            },
            {
                "name": "hermes_memory_feedback",
                "description": "Record feedback on memory quality.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                        "feedback_type": {"type": "string"},
                        "details": {"type": "string"},
                    },
                    "required": ["memory_id", "feedback_type"],
                },
            },
        ]

    def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        app = self._require_app()
        if name == "hermes_memory_search":
            return {
                "results": app.retriever.search(
                    arguments["query"],
                    limit=arguments.get("limit"),
                    source_types=arguments.get("source_types"),
                )
            }
        if name == "hermes_memory_add":
            return app.add_memory(
                memory_type=arguments["memory_type"],
                scope=arguments["scope"],
                title=arguments.get("title"),
                summary=arguments["summary"],
                canonical_text=arguments["canonical_text"],
                tags=arguments.get("tags"),
                entities=arguments.get("entities"),
            )
        if name == "hermes_memory_archive":
            app.store.archive_memory(arguments["memory_id"], arguments.get("reason"))
            return {"archived": True}
        if name == "hermes_memory_feedback":
            event_id = app.store.log_agent_learning_event(
                event_type="memory_feedback",
                summary=f"Memory feedback: {arguments['feedback_type']}",
                evidence=arguments,
            )
            return {"logged": True, "event_id": event_id}
        raise ValueError(f"Unknown memory tool: {name}")

    def system_prompt_block(self) -> str:
        return (
            "Hermes Memory OS is available for source-labeled local memory recall. "
            "Use injected memory as context, not as unquestioned truth."
        )

    def prefetch(self, query: str, context: dict[str, Any] | None = None) -> str:
        app = self._require_app()
        context = context or {}
        results = app.retriever.search(
            query,
            context=context,
            source_types=context.get("source_types"),
        )
        if not results:
            return ""
        lines = ["## Relevant Local Memory"]
        memory_ids = []
        for item in results:
            memory_ids.append(item["id"])
            source = item.get("citation") or _format_source(item.get("source"))
            title = item.get("title") or item["id"]
            summary = item.get("summary") or item.get("text", "")[:240]
            lines.append(f"- {summary} Source: {source}.")
            if title and title not in summary:
                lines[-1] = f"- {title}: {summary} Source: {source}."
        injected = "\n".join(lines)
        app.store.log_injection(memory_ids, injected)
        return injected

    def sync_turn(
        self,
        user_message: str,
        assistant_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        app = self._require_app()
        user_id, assistant_id = app.store.sync_turn(user_message, assistant_message, metadata)
        return {"raw_event_ids": [user_id, assistant_id]}

    def on_session_end(self, messages: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        app = self._require_app()
        event_id = app.store.log_agent_learning_event(
            event_type="session_end_review_candidate",
            summary="Session ended; review for durable memory extraction.",
            evidence={"message_count": len(messages), "metadata": metadata or {}},
        )
        return {"review_event_id": event_id}

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if action == "add":
            return self.handle_tool_call(
                "hermes_memory_add",
                {
                    "memory_type": (metadata or {}).get("memory_type", "fact"),
                    "scope": (metadata or {}).get("scope", "user"),
                    "title": target,
                    "summary": content,
                    "canonical_text": content,
                    "tags": (metadata or {}).get("tags", []),
                    "entities": (metadata or {}).get("entities", []),
                },
            )
        if action == "archive":
            return self.handle_tool_call("hermes_memory_archive", {"memory_id": target, "reason": content})
        raise ValueError(f"Unsupported memory write action: {action}")

    def _require_app(self) -> MemoryApp:
        if self.app is None:
            raise RuntimeError("Provider is not initialized.")
        return self.app


def create_provider(
    config: dict[str, Any] | str | Path | None = None,
    hermes_home: str | Path | None = None,
) -> HermesMemoryOSProvider:
    """Factory used by Hermes development/plugin loaders."""

    provider = HermesMemoryOSProvider()
    provider.initialize(config=config, hermes_home=hermes_home)
    return provider


def _format_source(source: Any) -> str:
    if not source:
        return "local memory"
    if isinstance(source, str) and source.strip() in {"[]", ""}:
        return "local memory"
    if isinstance(source, list):
        return ", ".join(str(item) for item in source) if source else "local memory"
    return str(source)
