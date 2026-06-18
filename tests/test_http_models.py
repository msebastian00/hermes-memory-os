import pytest

from hermes_memory_os.http_models import (
    expand_source_types,
    parse_adjacent_request,
    parse_candidate_request,
    parse_search_request,
)


def test_parse_search_request_bounds_and_aliases():
    request = parse_search_request(
        {
            "query": "Reachy recall",
            "source_types": ["memory", "note"],
            "limit": 99,
            "mode": "recall",
            "context": {"client": "reachy"},
        },
        max_query_chars=100,
        max_results=5,
    )

    assert request.query == "Reachy recall"
    assert request.source_types == ["memory", "note"]
    assert expand_source_types(request.source_types) == ["memory", "note", "wiki", "markdown"]
    assert request.limit == 5
    assert request.context == {"client": "reachy"}


def test_parse_search_request_rejects_invalid_input():
    with pytest.raises(ValueError, match="query_required"):
        parse_search_request({"query": ""}, max_query_chars=100, max_results=5)

    with pytest.raises(ValueError, match="query_too_large"):
        parse_search_request({"query": "x" * 101}, max_query_chars=100, max_results=5)

    with pytest.raises(ValueError, match="unsupported_source_type"):
        parse_search_request({"query": "x", "source_types": ["bad"]}, max_query_chars=100, max_results=5)

    with pytest.raises(ValueError, match="invalid_mode"):
        parse_search_request({"query": "x", "mode": "bad"}, max_query_chars=100, max_results=5)


def test_parse_adjacent_request():
    request = parse_adjacent_request(
        {"source_id": "src_1", "chunk_id": "chk_1", "direction": "around", "limit": 20},
        max_results=3,
    )

    assert request.source_id == "src_1"
    assert request.chunk_id == "chk_1"
    assert request.direction == "around"
    assert request.limit == 3


def test_parse_candidate_request_defaults_and_bounds():
    request = parse_candidate_request(
        {
            "content": "Mike prefers short answers.",
            "confidence": 3,
            "speaker": {"display_name": "Mike", "trusted": True},
        }
    )

    assert request.kind == "semantic"
    assert request.confidence == 1.0
    assert request.source == "reachy"
    assert request.speaker["display_name"] == "Mike"
