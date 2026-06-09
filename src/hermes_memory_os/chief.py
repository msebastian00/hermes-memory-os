"""Chief of Staff local workflow drafts."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from hermes_memory_os.app import MemoryApp
from hermes_memory_os.utils import now_iso


def process_inbox(
    app: MemoryApp,
    *,
    paths: Iterable[Path],
    output_dir: Path | None = None,
    limit: int = 8,
) -> Path:
    inbox_items = _read_inbox_items(paths)
    query = " ".join(item["text"] for item in inbox_items)[:2000] or "inbox review"
    results = app.retriever.search(query, limit=limit)
    lines = [
        "# Inbox Processing Draft",
        "",
        f"- Generated: {now_iso()}",
        f"- Items reviewed: {len(inbox_items)}",
        "",
        "## Inbox Items",
    ]
    if inbox_items:
        for item in inbox_items:
            lines.append(f"- `{item['path']}`: {_excerpt(item['text'])}")
    else:
        lines.append("- No inbox items found.")
    lines.extend(
        [
            "",
            "## Suggested Actions",
        ]
    )
    for item in inbox_items:
        actions = _extract_action_lines(item["text"])
        if actions:
            lines.append(f"- `{item['path']}`")
            lines.extend(f"  - {action}" for action in actions)
    if not any(_extract_action_lines(item["text"]) for item in inbox_items):
        lines.append("- Review each item and decide whether to archive, convert into a durable memory candidate, or connect to an active project.")
    lines.extend(_retrieval_section(results))
    return _write_draft(_output_dir(app, output_dir), "process-inbox", lines)


def daily_brief(app: MemoryApp, *, output_dir: Path | None = None, limit: int = 8) -> Path:
    events = app.store.list_recent_raw_events(limit=limit)
    memories = app.store.list_memories(limit=limit)
    query = " ".join([event["content"] for event in events] + [memory["summary"] for memory in memories])[:2000]
    results = app.retriever.search(query or "daily brief", limit=limit)
    lines = [
        "# Daily Brief Draft",
        "",
        f"- Generated: {now_iso()}",
        f"- Recent events: {len(events)}",
        f"- Active memories sampled: {len(memories)}",
        "",
        "## Active Themes",
    ]
    themes = _top_terms([event["content"] for event in events] + [memory["summary"] for memory in memories])
    lines.extend(f"- {theme}" for theme in themes) if themes else lines.append("- No active themes detected.")
    lines.extend(["", "## Recent Turns"])
    if events:
        for event in events:
            role = event.get("role") or event.get("source") or "event"
            lines.append(f"- `{event['id']}` {role}: {_excerpt(event['content'])}")
    else:
        lines.append("- No recent raw events.")
    lines.extend(["", "## Open Loops"])
    lines.extend(_open_loop_lines(events))
    lines.extend(_retrieval_section(results))
    return _write_draft(_output_dir(app, output_dir), "daily-brief", lines)


def weekly_connections(app: MemoryApp, *, output_dir: Path | None = None, limit: int = 12) -> Path:
    memories = app.store.list_memories(limit=limit * 2)
    terms = _top_terms([memory["summary"] + " " + memory["canonical_text"] for memory in memories], limit=12)
    query = " ".join(terms) or "weekly connections"
    results = app.retriever.search(query, limit=limit)
    lines = [
        "# Weekly Connections Draft",
        "",
        f"- Generated: {now_iso()}",
        f"- Memories sampled: {len(memories)}",
        "",
        "## Recurring Ideas",
    ]
    lines.extend(f"- {term}" for term in terms) if terms else lines.append("- No recurring ideas detected.")
    lines.extend(["", "## Memory Clusters"])
    if memories:
        for memory in memories[:limit]:
            tags = ", ".join(memory.get("tags") or []) or "untagged"
            lines.append(f"- {memory.get('title') or memory['id']}: {memory['summary']} Tags: {tags}.")
    else:
        lines.append("- No active memories available.")
    lines.extend(["", "## Possible Content Or Project Angles"])
    if terms:
        for term in terms[:5]:
            lines.append(f"- Explore how `{term}` connects to current projects, source material, and durable preferences.")
    else:
        lines.append("- Add or ingest more memory/source material before generating project angles.")
    lines.extend(_retrieval_section(results))
    return _write_draft(_output_dir(app, output_dir), "weekly-connections", lines)


def self_review(app: MemoryApp, *, output_dir: Path | None = None, limit: int = 20) -> Path:
    candidates = app.store.list_extraction_candidates(status="pending_review", limit=limit)
    learning_events = app.store.list_agent_learning_events(status="pending_review", limit=limit)
    lines = [
        "# Self-Review Draft",
        "",
        f"- Generated: {now_iso()}",
        f"- Pending extraction candidates: {len(candidates)}",
        f"- Pending learning events: {len(learning_events)}",
        "",
        "## Pending Extraction Candidates",
    ]
    if candidates:
        for candidate in candidates:
            lines.append(
                f"- `{candidate['id']}` [{candidate['memory_type']}/{candidate['scope']}]: "
                f"{candidate['summary']} Confidence: {candidate['confidence']}."
            )
    else:
        lines.append("- No pending extraction candidates.")
    lines.extend(["", "## Pending Learning Events"])
    if learning_events:
        for event in learning_events:
            lines.append(f"- `{event['id']}` {event['event_type']}: {event['summary']}")
    else:
        lines.append("- No pending learning events.")
    lines.extend(
        [
            "",
            "## Review Decisions",
            "- Approve, reject, or edit extraction candidates through `hermes-memory candidates update`.",
            "- Convert only reviewed candidates into durable memory.",
            "- Keep prompt, profile, and skill changes out of automatic workflows.",
        ]
    )
    return _write_draft(_output_dir(app, output_dir), "self-review", lines)


def _read_inbox_items(paths: Iterable[Path]) -> list[dict[str, str]]:
    items = []
    for path in paths:
        if path.is_dir():
            files = sorted(item for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            files = [path]
        else:
            continue
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            items.append({"path": str(file_path), "text": text})
    return items


def _output_dir(app: MemoryApp, output_dir: Path | None) -> Path:
    return output_dir or app.config.vault_dir / "chief"


def _write_draft(output_dir: Path, slug: str, lines: list[str]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_iso().replace(":", "").replace("+", "Z")
    path = output_dir / f"{stamp}-{slug}.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _retrieval_section(results: list[dict[str, Any]]) -> list[str]:
    lines = ["", "## Relevant Memory And Sources"]
    if not results:
        return lines + ["- No relevant retrieval results."]
    for item in results:
        citation = item.get("citation") or item.get("source") or "local memory"
        title = item.get("title") or item["id"]
        summary = item.get("summary") or _excerpt(item.get("text", ""))
        score = item.get("final_score")
        score_text = f" Score: {score}." if score is not None else ""
        lines.append(f"- `{item['kind']}:{item['id']}` {title}: {summary} Source: {citation}.{score_text}")
    return lines


def _extract_action_lines(text: str) -> list[str]:
    actions = []
    for line in text.splitlines():
        normalized = line.strip(" -\t")
        lowered = normalized.lower()
        if lowered.startswith(("todo", "action", "follow up", "follow-up")):
            actions.append(normalized)
    return actions[:8]


def _open_loop_lines(events: list[dict[str, Any]]) -> list[str]:
    lines = []
    for event in events:
        lowered = event["content"].lower()
        if "?" in event["content"] or any(marker in lowered for marker in ("todo", "follow up", "need to", "remind")):
            lines.append(f"- `{event['id']}`: {_excerpt(event['content'])}")
    return lines or ["- No open loops detected in recent events."]


def _top_terms(texts: list[str], *, limit: int = 8) -> list[str]:
    stop = {
        "about",
        "after",
        "again",
        "also",
        "and",
        "are",
        "for",
        "from",
        "hermes",
        "into",
        "should",
        "that",
        "the",
        "this",
        "with",
    }
    words = []
    for text in texts:
        words.extend(
            word
            for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower())
            if word not in stop
        )
    return [word for word, _ in Counter(words).most_common(limit)]


def _excerpt(text: str, *, length: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= length:
        return compact
    return compact[: length - 3].rstrip() + "..."
