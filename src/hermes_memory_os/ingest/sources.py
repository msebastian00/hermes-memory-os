"""General source ingestion for notes, books, and transcripts."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from hermes_memory_os.db.store import DEFAULT_CHUNKING_VERSION, MemoryStore
from hermes_memory_os.errors import ConfigError

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CHAPTER_RE = re.compile(r"^\s*(chapter|part|section)\s+[\wivxlcdm.-]+", re.IGNORECASE)
TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}(?::\d{2})?)\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}(?::\d{2})?)"
)
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".epub", ".srt", ".vtt", ".json"}


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    title: str
    source_type: str
    content: str
    chunks: list[dict[str, Any]]
    metadata: dict[str, Any]


def iter_source_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path
        elif path.is_dir():
            for suffix in sorted(SUPPORTED_SUFFIXES):
                yield from sorted(path.rglob(f"*{suffix}"))


def ingest_paths(
    store: MemoryStore,
    paths: Iterable[Path],
    *,
    source_type: str | None = None,
    reindex: bool = False,
) -> dict[str, int]:
    files = list(iter_source_files(paths))
    indexed = 0
    skipped = 0
    reindexed = 0
    for path in files:
        document = load_source_document(path, source_type=source_type)
        source_id, created = store.upsert_source_file(
            source_path=str(path),
            source_type=document.source_type,
            title=document.title,
            content=document.content,
            chunks=document.chunks,
            source_metadata=document.metadata,
            chunking_version=DEFAULT_CHUNKING_VERSION,
        )
        if created:
            indexed += 1
        else:
            skipped += 1
            if reindex:
                reindexed += store.mark_source_chunks_for_reindex(source_id=source_id)

    result = {"files_seen": len(files), "indexed": indexed, "skipped": skipped}
    if reindex:
        result["reindexed"] = reindexed
    return result


def load_source_document(path: Path, *, source_type: str | None = None) -> SourceDocument:
    suffix = path.suffix.lower()
    inferred_type = source_type or infer_source_type(path)
    if suffix == ".md":
        content = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(content)
    elif suffix == ".txt":
        content = path.read_text(encoding="utf-8")
        chunks = chunk_plain_text(content)
    elif suffix == ".srt":
        content = path.read_text(encoding="utf-8")
        chunks = chunk_subtitle(content, format_name="srt")
    elif suffix == ".vtt":
        content = path.read_text(encoding="utf-8")
        chunks = chunk_subtitle(content, format_name="vtt")
    elif suffix == ".json":
        content, chunks = load_json_transcript(path)
    elif suffix == ".epub":
        content = extract_epub_text(path)
        chunks = chunk_plain_text(content)
    elif suffix == ".pdf":
        content = extract_pdf_text(path)
        chunks = chunk_plain_text(content)
    else:
        raise ConfigError(f"Unsupported source file type: {path.suffix}")

    return SourceDocument(
        path=path,
        title=path.stem,
        source_type=inferred_type,
        content=content,
        chunks=chunks,
        metadata={"format": suffix.lstrip("."), "chunking_version": DEFAULT_CHUNKING_VERSION},
    )


def infer_source_type(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if suffix == ".md":
        return "wiki"
    if suffix == ".epub":
        return "book"
    if suffix in {".srt", ".vtt"}:
        return "subtitle"
    if suffix == ".json" or "transcript" in name or "transcripts" in parts:
        return "transcript"
    if suffix == ".txt":
        return "transcript" if "transcript" in name else "book"
    if suffix == ".pdf":
        return "article"
    return "source"


def chunk_markdown(text: str, *, max_chars: int = 1800) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_heading = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(line for line in buffer).strip()
        if content:
            for chunk in _split_large_chunk(content, max_chars=max_chars):
                chunk["heading"] = current_heading or ""
                chunk["section"] = current_heading
                chunks.append(chunk)
        buffer = []

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            buffer.append(line)
            continue
        buffer.append(line)
    flush()
    return chunks


def chunk_plain_text(text: str, *, max_chars: int = 1800) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_chapter = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            for chunk in _split_large_chunk(content, max_chars=max_chars):
                chunk["chapter"] = current_chapter
                chunk["section"] = current_chapter
                chunks.append(chunk)
        buffer = []

    for line in text.splitlines():
        if CHAPTER_RE.match(line):
            flush()
            current_chapter = line.strip()
        buffer.append(line)
    flush()
    return chunks


def chunk_subtitle(text: str, *, format_name: str) -> list[dict[str, Any]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if format_name == "vtt":
        normalized = re.sub(r"^WEBVTT.*?(?:\n\n|$)", "", normalized, flags=re.DOTALL)
    chunks = []
    for block in re.split(r"\n\s*\n", normalized.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines:
            continue
        match = TIMESTAMP_RE.search(lines[0])
        if not match:
            continue
        body = " ".join(lines[1:]).strip()
        if not body:
            continue
        speaker, body = _split_speaker(body)
        chunks.append(
            {
                "text": body,
                "timestamp_start": _normalize_timestamp(match.group("start")),
                "timestamp_end": _normalize_timestamp(match.group("end")),
                "speaker": speaker,
                "metadata": {"format": format_name},
            }
        )
    return chunks


def load_json_transcript(path: Path) -> tuple[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = _extract_json_segments(data)
    chunks = []
    content_parts = []
    for segment in segments:
        text = str(segment.get("text") or segment.get("content") or "").strip()
        if not text:
            continue
        speaker = segment.get("speaker") or segment.get("role")
        start = segment.get("start") or segment.get("timestamp_start") or segment.get("start_time")
        end = segment.get("end") or segment.get("timestamp_end") or segment.get("end_time")
        content_parts.append(text)
        chunks.append(
            {
                "text": text,
                "timestamp_start": _stringify_time(start),
                "timestamp_end": _stringify_time(end),
                "speaker": str(speaker) if speaker else None,
                "metadata": {"format": "json"},
            }
        )
    return "\n\n".join(content_parts), chunks


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise ConfigError("PDF ingestion requires local dependency `pypdf` to be installed.") from exc

    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"\n\n[Page {index}]\n{text.strip()}")
    return "\n".join(pages).strip()


def extract_epub_text(path: Path) -> str:
    sections = []
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".xhtml", ".html", ".htm"))
        ]
        for name in sorted(names):
            raw = archive.read(name).decode("utf-8", errors="ignore")
            text = _html_to_text(raw)
            if text:
                sections.append(text)
    if not sections:
        raise ConfigError(f"No readable XHTML/HTML content found in EPUB: {path}")
    return "\n\n".join(sections)


def _split_large_chunk(text: str, *, max_chars: int) -> list[dict[str, Any]]:
    if len(text) <= max_chars:
        return [{"text": text}]

    pieces = []
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    current = []
    current_len = 0
    for paragraph in paragraphs:
        if current and current_len + len(paragraph) + 2 > max_chars:
            pieces.append({"text": "\n\n".join(current)})
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 2
    if current:
        pieces.append({"text": "\n\n".join(current)})
    return pieces


def _extract_json_segments(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("segments", "items", "utterances", "transcript", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if "text" in data or "content" in data:
        return [data]
    return []


def _split_speaker(text: str) -> tuple[str | None, str]:
    match = re.match(r"^([A-Za-z][\w .-]{0,48}):\s+(.+)$", text)
    if not match:
        return None, text
    return match.group(1).strip(), match.group(2).strip()


def _normalize_timestamp(value: str) -> str:
    return value.replace(",", ".")


def _stringify_time(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _html_to_text(raw: str) -> str:
    parser = _TextHTMLParser()
    parser.feed(raw)
    return "\n".join(parser.parts).strip()
