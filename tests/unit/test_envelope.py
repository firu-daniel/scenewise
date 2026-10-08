import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scenewise.app.contract.envelope import parse, request_digest


def test_parse_reads_the_envelope_only() -> None:
    raw = json.dumps(
        {"job_id": "j-1", "schema_version": "1", "external_ref": {"a": "b"}, "x": [1]}
    ).encode()
    envelope = parse(raw)
    assert envelope is not None
    assert envelope.job_id == "j-1"
    assert envelope.schema_version == "1"
    assert envelope.external_ref == (("a", "b"),)
    assert envelope.request_digest == request_digest(json.loads(raw))


@pytest.mark.parametrize(
    "raw",
    [b"not json", b"[1, 2]", b"{}", b'{"job_id": ".."}', b'{"job_id": 3}'],
)
def test_parse_without_a_usable_job_id(raw: bytes) -> None:
    assert parse(raw) is None


@pytest.mark.parametrize("ref", [{"a": 1}, ["a"], "a", None])
def test_external_ref_is_lenient(ref: object) -> None:
    raw = json.dumps({"job_id": "j", "schema_version": 1, "external_ref": ref})
    envelope = parse(raw.encode())
    assert envelope is not None
    assert envelope.external_ref is None
    assert envelope.schema_version is None


json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda inner: st.lists(inner) | st.dictionaries(st.text(), inner),
    max_leaves=10,
)


@given(st.dictionaries(st.text(), json_values, max_size=6))
def test_digest_ignores_key_order_and_whitespace(document: dict[str, object]) -> None:
    reordered = dict(reversed(list(document.items())))
    spaced = json.loads(json.dumps(reordered, indent=2))
    assert request_digest(document) == request_digest(spaced)
