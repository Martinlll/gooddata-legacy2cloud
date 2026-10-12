# (C) 2026 GoodData Corporation
"""
This test aims to verify the transformation of Legacy metrics to Cloud metrics.

All calls to Legacy and Cloud are mocked, the data is loaded from JSON files stored
in the `tests/data/metrics` directory.

The test verifies that the transformation of Legacy metrics metadata matches
the expected Cloud metrics metadata.
"""

import pytest

from gooddata_legacy2cloud.metrics.cloud_metrics_builder import CloudMetricsBuilder
from tests.test_utils import dicts_are_equal, load_json

TEST_CASES_DIR = "tests/data/metrics/test_cases"


@pytest.mark.parametrize(
    "case_file_name",
    [
        "basic_metric",
        "with_nonexistent_value_in_filter",
        "with_date_filters",
        "using_deprecated_metric",
        "with_unresolved_identifier",
        "with_computed_attribute",
    ],
)
def test_metrics_migration(
    case_file_name: str,
    metrics_builder: CloudMetricsBuilder,
) -> None:
    """Test the transformation of Legacy metrics to Cloud metrics.

    To add a test case, add its name to the test parameters and create two files
    in the `tests/data/metrics/test_cases` directory:
    - <case_file_name>_legacy.json - Legacy metrics metadata
    - <case_file_name>_cloud.json - Expected Cloud metrics metadata
    """

    # Load Legacy metrics
    legacy_metrics = load_json(f"{TEST_CASES_DIR}/{case_file_name}_legacy.json")
    assert isinstance(legacy_metrics, list), "Legacy metrics should be a list"

    # Load expected Cloud metrics
    expected_cloud_metrics = load_json(f"{TEST_CASES_DIR}/{case_file_name}_cloud.json")
    assert isinstance(expected_cloud_metrics, list), "Cloud metrics should be a list"

    # Process Legacy metrics
    metrics_builder.process_legacy_metrics(legacy_metrics)

    # Get Cloud metrics
    actual_cloud_metrics = metrics_builder.get_cloud_metrics()

    # Compare the actual data with expected_cloud_metrics
    # Sort both lists for comparison (metrics may be sorted differently)
    actual_sorted = sorted(actual_cloud_metrics, key=lambda x: x["data"]["id"])
    expected_sorted = sorted(expected_cloud_metrics, key=lambda x: x["data"]["id"])

    if len(actual_sorted) != len(expected_sorted):
        pytest.fail(
            f"Metric count mismatch: actual={len(actual_sorted)}, expected={len(expected_sorted)}"
        )

    for actual, expected in zip(actual_sorted, expected_sorted):
        dicts_are_equal(actual, expected)
        dicts_are_equal(expected, actual)
