"""OpenNotebook — Unit tests for the Qdrant payload index schema."""

from __future__ import annotations

from app.infrastructure.qdrant.schema import (
    PAYLOAD_INDEX_FIELD_TYPE,
    PAYLOAD_INDEX_FIELDS,
    dimension_matches,
)


def test_required_filter_fields_are_indexed():
    required = {
        "notebook_id",
        "source_id",
        "workspace_id",
        "sensitivity_level",
        "allowed_roles",
        "allowed_users",
    }
    assert required.issubset(set(PAYLOAD_INDEX_FIELDS))


def test_no_duplicate_fields():
    assert len(PAYLOAD_INDEX_FIELDS) == len(set(PAYLOAD_INDEX_FIELDS))


def test_field_names_are_snake_case():
    for field in PAYLOAD_INDEX_FIELDS:
        assert field == field.lower()
        assert " " not in field


def test_index_type_is_keyword():
    assert PAYLOAD_INDEX_FIELD_TYPE == "keyword"


def test_dimension_matches():
    assert dimension_matches(384, None) is True
    assert dimension_matches(384, 384) is True
    assert dimension_matches(384, 1536) is False
