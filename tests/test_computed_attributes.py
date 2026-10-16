# (C) 2026 GoodData Corporation
"""
Verifies the transformation of Legacy computed attributes to Cloud ones.
All calls to Legacy and Cloud are mocked, data is loaded from `tests/data/metrics`.
"""

import dataclasses

import pytest

from gooddata_legacy2cloud.helpers import cloud_display_form_type
from gooddata_legacy2cloud.id_mappings import IdMappings
from gooddata_legacy2cloud.output_writer import OutputWriter
from gooddata_legacy2cloud.metrics.computed_attribute import (
    build_cloud_computed_attribute,
    build_cloud_computed_attributes,
)
from tests.test_utils import dicts_are_equal, load_json

LEGACY_FILE = "tests/data/metrics/legacy_objects/computed_attribute.json"
CLOUD_FILE = "tests/data/metrics/test_cases/computed_attribute_cloud.json"
METRIC_MAPPINGS = "tests/data/metrics/mapping_files/metric_mappings.csv"


@pytest.fixture
def ca_context(metrics_context):
    return dataclasses.replace(
        metrics_context, metric_mappings=IdMappings(METRIC_MAPPINGS)
    )


def test_computed_attribute_transformation(ca_context) -> None:
    attribute, expected = load_json(LEGACY_FILE), load_json(CLOUD_FILE)
    assert isinstance(attribute, dict) and isinstance(expected, dict)
    actual = build_cloud_computed_attribute(ca_context, attribute)
    dicts_are_equal(actual, expected)
    dicts_are_equal(expected, actual)


def test_unsupported_definition_is_skipped(ca_context) -> None:
    attribute = load_json(LEGACY_FILE)
    assert isinstance(attribute, dict)
    attribute["attribute"]["content"]["rel"] = [
        "to {attr.segment.segmentkey} as case when {aeB03p0tbrQw} "
        'between 1 and 9 then {attr.comp.h29rLOz?"x"} end'
    ]
    with pytest.raises(ValueError, match="Unsupported"):
        build_cloud_computed_attribute(ca_context, attribute)
    assert build_cloud_computed_attributes(ca_context, [attribute]) == []


def test_computed_attribute_ids_and_types() -> None:
    mappings = IdMappings()
    assert mappings.search_mapping_identifier("attr.comp.X") == "label.comp.X"
    assert mappings.search_mapping_identifier("label.comp.X") == "label.comp.X"
    with pytest.raises(ValueError):
        mappings.search_mapping_identifier("attr.other.X")
    assert cloud_display_form_type("label.comp.X") == "computedAttribute"
    assert cloud_display_form_type("label.products.category") == "label"


def test_skipped_computed_attributes_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    OutputWriter("unused.csv").write_skipped_objects([], "computed_attribute")
    assert (tmp_path / "cloud_skipped_computed_attributes.json").exists()
