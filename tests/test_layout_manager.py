# (C) 2026 GoodData Corporation
"""Creator/modifier updates in the Cloud layout for dashboards, metrics, insights."""

from typing import Any

from gooddata_legacy2cloud.layout.layout_manager import (
    update_object_creators_in_layout,
)
from gooddata_legacy2cloud.user_management.data_classes import ObjectUpdate
from gooddata_legacy2cloud.user_management.legacy_users import (
    extract_creator_modifier_ids,
)

OLD = {"id": "old", "type": "user"}


def _update(object_type: str, cloud_id: str, modifier: str | None) -> ObjectUpdate:
    return ObjectUpdate(
        legacy_object_id=cloud_id,
        legacy_object_title=cloud_id,
        cloud_object_id=cloud_id,
        object_type=object_type,
        legacy_creator_id="legacy-a",
        legacy_modifier_id="legacy-c" if modifier else None,
        cloud_creator_id="author",
        cloud_modifier_id=modifier,
    )


def test_creators_updated_for_all_object_types() -> None:
    layout: dict[str, dict[str, list[dict[str, Any]]]] = {
        "analytics": {
            "analyticalDashboards": [
                {"id": "d1", "title": "D", "createdBy": OLD, "modifiedBy": OLD}
            ],
            "metrics": [
                {"id": "m1", "title": "M", "createdBy": OLD, "modifiedBy": OLD}
            ],
            "visualizationObjects": [{"id": "i1", "title": "I", "createdBy": OLD}],
        }
    }
    updates = [
        _update("dashboard", "d1", "contributor"),
        _update("metric", "m1", None),
        _update("insight", "i1", "contributor"),
        _update("metric", "missing", None),
    ]
    _, made, not_found, changes = update_object_creators_in_layout(layout, updates)
    a = layout["analytics"]
    assert (made, not_found) == (3, 1)
    assert a["analyticalDashboards"][0]["createdBy"]["id"] == "author"
    assert a["analyticalDashboards"][0]["modifiedBy"]["id"] == "contributor"
    assert a["analyticalDashboards"][0]["permissions"][0]["assignee"]["id"] == "author"
    assert a["metrics"][0]["modifiedBy"]["id"] == "author"  # no modifier -> creator
    assert a["visualizationObjects"][0]["createdBy"]["id"] == "author"
    assert "modifiedBy" not in a["visualizationObjects"][0]
    assert "permissions" not in a["metrics"][0]
    assert {c.object_type for c in changes if c.change_type == "creator_updated"} == {
        "dashboard",
        "metric",
        "insight",
    }


def test_contributor_is_collected_as_modifier() -> None:
    objects = [
        {
            "metric": {
                "meta": {
                    "author": "/gdc/account/profile/aaa",
                    "contributor": "/gdc/account/profile/bbb",
                }
            }
        }
    ]
    assert extract_creator_modifier_ids(objects) == {"aaa", "bbb"}
