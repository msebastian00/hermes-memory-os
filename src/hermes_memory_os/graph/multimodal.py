"""Additive PDF visual-evidence extraction through a configured local VLM."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import requests


class MultimodalError(RuntimeError):
    """Raised when visual evidence cannot be extracted safely."""


def configured() -> bool:
    return bool(os.environ.get("HERMES_GRAPH_VLM_BASE_URL"))


def render_pdf_pages(pdf_path: Path, output_dir: Path, *, first_page: int = 1, last_page: int | None = None) -> list[Path]:
    """Render immutable PDF pages locally; no OCR or model call occurs here."""
    if first_page < 1 or last_page is not None and last_page < first_page:
        raise MultimodalError("PDF page range is invalid.")
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    try:
        command = ["pdftoppm", "-png", "-f", str(first_page)]
        if last_page is not None:
            command.extend(["-l", str(last_page)])
        command.extend([str(pdf_path), str(prefix)])
        subprocess.run(command, check=True, capture_output=True, text=True)
        return sorted(output_dir.glob("page-*.png"))
    except FileNotFoundError:
        # Hermes Core includes PyMuPDF even when the optional Poppler CLI is absent.
        try:
            import fitz
        except ImportError as exc:
            raise MultimodalError("PDF rendering requires pdftoppm or PyMuPDF.") from exc
        document = fitz.open(pdf_path)
        try:
            final_page = min(last_page or document.page_count, document.page_count)
            pages: list[Path] = []
            for page_number in range(first_page, final_page + 1):
                image_path = output_dir / f"page-{page_number:04d}.png"
                document.load_page(page_number - 1).get_pixmap(dpi=200, alpha=False).save(image_path)
                pages.append(image_path)
            return pages
        finally:
            document.close()


def analyze_image(image_path: Path, *, prompt: str, timeout: int = 120) -> dict[str, Any]:
    """Request constrained visual extraction from Spark 1's OpenAI-compatible VLM."""
    base_url = os.environ.get("HERMES_GRAPH_VLM_BASE_URL", "").rstrip("/")
    if not base_url:
        raise MultimodalError("HERMES_GRAPH_VLM_BASE_URL is required for visual analysis.")
    model = os.environ.get("HERMES_GRAPH_VLM_MODEL", "qwen36")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
        ]}],
    }
    response = requests.post(f"{base_url}/chat/completions", json=payload, timeout=timeout)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    try:
        result = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MultimodalError("VLM did not return a JSON evidence record.") from exc
    if not isinstance(result, dict):
        raise MultimodalError("VLM evidence record must be a JSON object.")
    result.update({
        "attachment_path": str(image_path),
        "attachment_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "extractor": f"spark1:{model}",
    })
    return result


def write_evidence_record(record: dict[str, Any], output_path: Path) -> Path:
    """Persist a reviewed artifact for later graph validation/upsert."""
    required = {"attachment_path", "attachment_sha256", "extractor", "confidence"}
    missing = sorted(key for key in required if key not in record)
    if missing:
        raise MultimodalError(f"Evidence record missing required fields: {', '.join(missing)}")
    confidence = float(record["confidence"])
    if not 0 <= confidence <= 1:
        raise MultimodalError("Evidence confidence must be between 0 and 1.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def visual_evidence_plan(
    config: Any,
    source_id: str,
    records: list[dict[str, Any]],
    *,
    min_confidence: float = 0.75,
) -> dict[str, Any]:
    """Create an idempotent Evidence/Claim plan from immutable visual artifacts.

    The VLM may describe a page but never receives authority to replace source
    text. A record is graphable only when its attachment hash, source page,
    provenance, and confidence can be verified locally.
    """
    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be between 0 and 1.")

    from hermes_memory_os.utils import now_iso
    from .builder import discover_book
    from .ids import claim_id, chunk_id, document_id, entity_id, evidence_id, relationship_id

    book = discover_book(config.vault_root, source_id)
    raw_document_id = document_id(book.source_id, book.raw_relative_path)
    book_entity_id = entity_id("book", book.title)
    chunks_by_page: dict[int, tuple[dict[str, Any], str]] = {}
    chunk_ids_by_index: dict[int, str] = {}
    for chunk in book.chunks:
        text_hash = hashlib.sha256(json.dumps(chunk, sort_keys=True).encode("utf-8")).hexdigest()
        graph_chunk_id = chunk_id(raw_document_id, int(chunk["chunk_index"]), text_hash)
        chunk_ids_by_index[int(chunk["chunk_index"])] = graph_chunk_id
        start, end = chunk.get("page_start"), chunk.get("page_end")
        if isinstance(start, int) and isinstance(end, int):
            for page in range(start, end + 1):
                chunks_by_page.setdefault(page, (chunk, graph_chunk_id))

    nodes: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    warnings: list[str] = []
    visual_records: list[dict[str, Any]] = []
    for record in records:
        required = ("attachment_path", "attachment_sha256", "extractor", "confidence", "page_number", "description")
        missing = [
            key for key in required
            if key not in record or record[key] is None
            or (isinstance(record[key], str) and not record[key].strip())
        ]
        if missing:
            warnings.append("visual_evidence_missing:" + ",".join(missing))
            continue
        if str(record.get("modality", "")).strip().lower() == "none":
            warnings.append(f"visual_evidence_empty_page:page={record['page_number']}")
            continue
        try:
            confidence = float(record["confidence"])
            page = int(record["page_number"])
        except (TypeError, ValueError):
            warnings.append("visual_evidence_invalid_confidence_or_page")
            continue
        if not 0 <= confidence <= 1:
            warnings.append(f"visual_evidence_invalid_confidence:page={page}")
            continue
        if confidence < min_confidence:
            warnings.append(f"visual_evidence_low_confidence:page={page}")
            continue
        matched = chunks_by_page.get(page)
        if matched is None:
            matched = _match_page_text_to_chunk(
                book,
                str(record.get("page_text") or record.get("visible_text") or ""),
                chunk_ids_by_index,
            )
        if matched is None:
            warnings.append(f"visual_evidence_unmapped_page:{page}")
            continue
        _, graph_chunk_id = matched
        attachment = Path(str(record["attachment_path"]))
        if not attachment.is_file() or hashlib.sha256(attachment.read_bytes()).hexdigest() != record["attachment_sha256"]:
            warnings.append(f"visual_evidence_attachment_mismatch:page={page}")
            continue

        description = str(record["description"]).strip()
        claim_text = str(record.get("claim_text") or description).strip()
        if not claim_text:
            warnings.append(f"visual_evidence_empty_claim:page={page}")
            continue
        visual_hash = str(record["attachment_sha256"])
        visual_evidence_id = evidence_id(graph_chunk_id, page, page, visual_hash)
        visual_claim_id = claim_id(visual_hash, f"visual:{source_id}")
        created_at = now_iso()
        locator = f"{book.raw_relative_path}#page={page}"
        nodes.extend((
            {
                "label": "Claim",
                "id": visual_claim_id,
                "properties": {
                    "id": visual_claim_id,
                    "claim_text": claim_text,
                    "normalized_text": _normalize_claim(claim_text),
                    "claim_type": "visual_source_claim",
                    "claim_basis": "visual source extraction",
                    "scope": "source",
                    "confidence": confidence,
                    "status": "active",
                    "verification_status": "visual_provenance_verified",
                    "asserted_by": list(book.authors),
                    "source_quality": "derived from immutable source page",
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            },
            {
                "label": "Evidence",
                "id": visual_evidence_id,
                "properties": {
                    "id": visual_evidence_id,
                    "source_id": source_id,
                    "document_id": raw_document_id,
                    "chunk_id": graph_chunk_id,
                    "quote": description,
                    "span_start": 0,
                    "span_end": 0,
                    "evidence_type": "derived",
                    "confidence": confidence,
                    "created_at": created_at,
                    "source_locator": locator,
                    "extracted_by": str(record["extractor"]),
                    "modality": str(record.get("modality") or "visual"),
                    "page_number": page,
                    "attachment_path": str(attachment),
                    "attachment_sha256": visual_hash,
                    "latex": str(record.get("latex") or ""),
                },
            },
        ))
        visual_records.append({
            "source_id": source_id,
            "page_number": page,
            "attachment_sha256": visual_hash,
            "evidence_id": visual_evidence_id,
            "claim_id": visual_claim_id,
        })
        for relation_type, from_id, to_id in (
            ("SUPPORTS", graph_chunk_id, visual_claim_id),
            ("SUPPORTS", visual_evidence_id, visual_claim_id),
            ("ABOUT", visual_claim_id, book_entity_id),
        ):
            relation_id = relationship_id(relation_type, from_id, to_id, visual_evidence_id)
            relationships.append({
                "id": relation_id,
                "type": relation_type,
                "from_id": from_id,
                "to_id": to_id,
                "properties": {
                    "id": relation_id,
                    "confidence": confidence,
                    "source": "hermes-graph:multimodal-v1",
                    "evidence_id": visual_evidence_id,
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            })

    return {
        "source_id": source_id,
        "status": "planned",
        "nodes": nodes,
        "relationships": relationships,
        "visual_records": visual_records,
        "warnings": sorted(set(warnings)),
    }


def _normalize_claim(value: str) -> str:
    return " ".join(value.lower().split())


VISUAL_EVIDENCE_PROMPT = """Extract only visible, source-supported information from this book page.
Return one JSON object with:
- modality: one of diagram, table, chart, equation, image, mixed, none
- description: concise factual description of the visual content
- claim_text: one conservative claim directly supported by the page, or the description
- latex: normalized LaTeX only for a visible equation; otherwise an empty string
- visible_text: only text visibly present on the page, or an empty string
- confidence: number from 0 to 1
Do not infer facts absent from the page. Do not include Markdown."""


def extract_pdf_visual_evidence(
    pdf_path: Path,
    output_dir: Path,
    *,
    first_page: int = 1,
    last_page: int | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Render PDF pages and retain only evidence records with immutable provenance."""
    if not pdf_path.is_file():
        raise MultimodalError(f"PDF does not exist: {pdf_path}")
    pages = render_pdf_pages(pdf_path, output_dir / "pages", first_page=first_page, last_page=last_page)
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    page_text = _pdf_page_text(pdf_path, first_page=first_page, last_page=last_page)
    for image_path in pages:
        try:
            page_number = int(image_path.stem.rsplit("-", 1)[1])
            record = analyze_image(image_path, prompt=VISUAL_EVIDENCE_PROMPT, timeout=timeout)
            record["page_number"] = page_number
            if page_text.get(page_number):
                record["page_text"] = page_text[page_number]
            record_path = output_dir / "records" / f"page-{page_number:04d}.json"
            persisted_record = {key: value for key, value in record.items() if key != "page_text"}
            write_evidence_record(persisted_record, record_path)
            records.append(record)
        except (ValueError, OSError, requests.RequestException, MultimodalError) as exc:
            warnings.append(f"visual_evidence_failed:{image_path.name}:{exc}")
    return {
        "pdf_path": str(pdf_path),
        "pages_rendered": len(pages),
        "records": records,
        "warnings": warnings,
    }


def _pdf_page_text(pdf_path: Path, *, first_page: int, last_page: int | None) -> dict[int, str]:
    """Read an existing PDF text layer solely to prove a page-to-raw-span mapping."""
    try:
        import fitz
    except ImportError:
        return {}
    document = fitz.open(pdf_path)
    try:
        final_page = min(last_page or document.page_count, document.page_count)
        return {
            page_number: document.load_page(page_number - 1).get_text("text")
            for page_number in range(first_page, final_page + 1)
        }
    finally:
        document.close()


def _match_page_text_to_chunk(
    book: Any,
    page_text: str,
    chunk_ids_by_index: dict[int, str],
) -> tuple[dict[str, Any], str] | None:
    """Map a page only when a unique visible phrase occurs in one raw-source span."""
    words = re.findall(r"[\w]+", _searchable_text(page_text), flags=re.UNICODE)
    if len(words) < 8:
        return None
    raw_text, raw_offsets = _searchable_text(book.raw_path.read_text(encoding="utf-8"), with_offsets=True)
    for window_size in (16, 12, 8):
        for start_index in range(0, len(words) - window_size + 1, max(1, window_size // 2)):
            phrase = r"\W+".join(re.escape(word) for word in words[start_index : start_index + window_size])
            matches = list(re.finditer(phrase, raw_text, flags=re.UNICODE))
            if len(matches) != 1:
                continue
            offset = raw_offsets[matches[0].start()]
            for chunk in book.chunks:
                span_start = chunk.get("span_start")
                span_end = chunk.get("span_end")
                if isinstance(span_start, int) and isinstance(span_end, int) and span_start <= offset < span_end:
                    return chunk, chunk_ids_by_index[int(chunk["chunk_index"])]
    return None


def _searchable_text(value: str, *, with_offsets: bool = False) -> str | tuple[str, list[int]]:
    """Normalize line-break hyphenation while preserving raw offsets for span proof."""
    output: list[str] = []
    offsets: list[int] = []
    index = 0
    while index < len(value):
        char = value[index]
        if (
            char == "-"
            and index > 0
            and value[index - 1].isalnum()
            and index + 1 < len(value)
        ):
            next_index = index + 1
            while next_index < len(value) and value[next_index].isspace():
                next_index += 1
            if next_index < len(value) and value[next_index].isalnum():
                index = next_index
                continue
        output.append(char.casefold())
        offsets.append(index)
        index += 1
    text = "".join(output)
    return (text, offsets) if with_offsets else text


def visual_processing_enabled() -> bool:
    """Require an explicit local switch before queued promotion invokes a VLM."""
    return os.environ.get("HERMES_GRAPH_VISUAL_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"} and configured()


def discover_book_pdf(book: Any, vault_root: Path) -> Path | None:
    """Resolve an immutable PDF declared by a book manifest without moving it."""
    from .builder import _read_frontmatter

    manifest, _ = _read_frontmatter(book.manifest_path)
    candidates = [
        manifest.get("original_path"),
        manifest.get("companion_pdf"),
        manifest.get("pdf_path"),
    ]
    candidates.append(str(book.raw_path.with_suffix(".pdf").relative_to(vault_root)) if book.raw_path.with_suffix(".pdf").is_file() else None)
    for value in candidates:
        if not value:
            continue
        candidate_path = Path(str(value))
        candidate = candidate_path.resolve() if candidate_path.is_absolute() else (vault_root / candidate_path).resolve()
        if candidate.suffix.lower() == ".pdf" and candidate.is_file() and vault_root.resolve() in candidate.parents:
            return candidate
    return None
