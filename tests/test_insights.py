# (C) 2026 GoodData Corporation
"""
This test aims to verify the transformation of Legacy insights to Cloud insights.

All calls to Legacy and Cloud are mocked, the data is loaded from JSON files stored
in the `tests/data/insights` directory.

The test verifies that the transformation of Legacy insights metadata matches
the expected Cloud insights metadata.
"""

import pytest
from gooddata_legacy2cloud.insights.cloud_insights_builder import CloudInsightsBuilder
from tests.test_utils import dicts_are_equal, load_json

TEST_CASES_DIR = "tests/data/insights/test_cases"


@pytest.mark.parametrize(
    "case_file_name",
    [
        "basic_insight",
        "with_computed_attribute",
        "with_missing_value_in_color_definition",
        "with_metric_value_filter",
        "with_top_filter",
        "headline_as_a_kpi",
        "has_all_additional_date_labels_gd_date",
        "using_deprecated_metric",
    ],
)
def test_insights_migration(
    case_file_name: str,
    insights_builder: CloudInsightsBuilder,
) -> None:
    """Test the transformation of Legacy insights to Cloud insights.

    To add a test case, add its name to the test parameters and create two files
    in the `tests/data/insights/test_cases` directory:
    - <case_file_name>_legacy.json - Legacy insights metadata
    - <case_file_name>_cloud.json - Expected Cloud insights metadata
    """

    # Load Legacy insights
    legacy_insights = load_json(f"{TEST_CASES_DIR}/{case_file_name}_legacy.json")
    assert isinstance(legacy_insights, list), "Legacy insights should be a list"

    # Load expected Cloud insights
    expected_cloud_insights = load_json(f"{TEST_CASES_DIR}/{case_file_name}_cloud.json")
    assert isinstance(expected_cloud_insights, list), "Cloud insights should be a list"

    # Process Legacy insights
    insights_builder.process_legacy_insights(legacy_insights)

    # Get Cloud insights
    actual_cloud_insights = insights_builder.get_cloud_insights()

    # Filter out None values (insights that couldn't be migrated)
    actual_cloud_insights = [i for i in actual_cloud_insights if i is not None]

    # Compare the actual data with expected_cloud_insights
    # Sort both lists for comparison
    actual_sorted = sorted(actual_cloud_insights, key=lambda x: x["data"]["id"])
    expected_sorted = sorted(expected_cloud_insights, key=lambda x: x["data"]["id"])

    if len(actual_sorted) != len(expected_sorted):
        pytest.fail(
            f"Insight count mismatch: actual={len(actual_sorted)}, expected={len(expected_sorted)}"
        )

    for actual, expected in zip(actual_sorted, expected_sorted):
        dicts_are_equal(actual, expected)
        dicts_are_equal(expected, actual)


def test_insight_keep_original_ids(insights_context_keep_ids) -> None:
    """When keep_original_ids=True, cloud ID equals the Legacy identifier."""
    builder = CloudInsightsBuilder(insights_context_keep_ids)
    legacy_insights = load_json(f"{TEST_CASES_DIR}/basic_insight_legacy.json")
    assert isinstance(legacy_insights, list), "Insights should be a list"
    builder.process_legacy_insights(legacy_insights)
    cloud_insights = builder.get_cloud_insights()

    assert len(cloud_insights) == len(legacy_insights)
    for cloud_insight, legacy_insight in zip(cloud_insights, legacy_insights):
        legacy_id = legacy_insight["visualizationObject"]["meta"]["identifier"]
        assert cloud_insight["data"]["id"] == legacy_id
