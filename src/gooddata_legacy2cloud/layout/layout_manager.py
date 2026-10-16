# (C) 2026 GoodData Corporation
"""Layout management utilities for working with Cloud workspace layouts."""

import logging

from gooddata_legacy2cloud.dashboard_permissions.change_formatter import (
    format_change_line,
)
from gooddata_legacy2cloud.dashboard_permissions.data_classes import ActualChange
from gooddata_legacy2cloud.user_management.data_classes import ObjectUpdate

logger = logging.getLogger("migration")

LAYOUT_SECTIONS = {
    "dashboard": "analyticalDashboards",
    "metric": "metrics",
    "insight": "visualizationObjects",
}


def find_dashboard_in_layout(layout: dict, dashboard_id: str) -> dict | None:
    """
    Finds a dashboard in the layout by ID.

    Args:
        layout: The workspace layout dictionary
        dashboard_id: The dashboard ID to find

    Returns:
        dict: The dashboard object if found, None otherwise
    """
    # Navigate to analyticalDashboards section
    analytics = layout.get("analytics", {})
    analytical_dashboards = analytics.get("analyticalDashboards", [])

    for dashboard in analytical_dashboards:
        if dashboard.get("id") == dashboard_id:
            return dashboard

    return None


def update_object_creators_in_layout(
    layout: dict,
    object_updates: list[ObjectUpdate],
    skip_creators: bool = False,
    skip_individual_grantees: bool = False,
    skip_group_grantees: bool = False,
    permission_level: str = "EDIT",
    keep_existing_permissions: bool = False,
) -> tuple[dict, int, int, list[ActualChange]]:
    """
    Updates creator fields and permissions in the layout for specified objects.

    Modifies the createdBy field and modifiedBy field (if present) of dashboards,
    metrics and insights, and permissions of dashboards, leaving all other
    sections and fields untouched.

    Args:
        layout: The workspace layout dictionary
        object_updates: List of ObjectUpdate instances with mapping information
        skip_creators: If True, skip migrating creator permissions
        skip_individual_grantees: If True, skip migrating individual user grantees
        skip_group_grantees: If True, skip migrating user group grantees
        permission_level: Permission level to assign to grantees (VIEW, SHARE, or EDIT)
        keep_existing_permissions: If True, keep permissions not in source instead of removing

    Returns:
        tuple: (modified_layout, number_of_updates_made, number_not_found_in_layout, actual_changes)
    """
    updates_made = 0
    actual_changes: list[ActualChange] = []
    analytics = layout.get("analytics", {})

    # Create a mapping of (object type, Cloud ID) to update info
    update_map = {(obj.object_type, obj.cloud_object_id): obj for obj in object_updates}
    found_keys = set()

    for object_type, section in LAYOUT_SECTIONS.items():
        for obj in analytics.get(section, []):
            key = (object_type, obj.get("id"))
            if key not in update_map:
                continue
            update_info = update_map[key]
            title = obj.get("title", "Untitled")
            changes = _update_creator_fields(
                obj, key[1], title, update_info, skip_creators
            )
            if object_type == "dashboard":
                changes.extend(
                    _sync_permissions(
                        obj,
                        key[1],
                        title,
                        update_info,
                        skip_creators,
                        skip_individual_grantees,
                        skip_group_grantees,
                        permission_level,
                        keep_existing_permissions,
                    )
                )
            for change in changes:
                actual_changes.append(change)
                logger.info("%s", format_change_line(change))
            updates_made += 1
            found_keys.add(key)

    not_found_count = len(update_map) - len(found_keys)

    return layout, updates_made, not_found_count, actual_changes


def _update_creator_fields(
    dashboard: dict,
    dashboard_id: str,
    dashboard_title: str,
    update_info: ObjectUpdate,
    skip_creators: bool,
) -> list[ActualChange]:
    """Update createdBy (Legacy author) and modifiedBy (Legacy contributor)."""
    if skip_creators or not update_info.has_creator_mapping:
        return []
    new_creator = update_info.cloud_creator_id or ""
    new_modifier = update_info.cloud_modifier_id or new_creator
    old_creator = dashboard.get("createdBy", {}).get("id", "None")
    old_modifier = dashboard.get("modifiedBy", {}).get("id", new_modifier)
    if old_creator == new_creator and old_modifier == new_modifier:
        return []
    dashboard["createdBy"] = {"id": new_creator, "type": "user"}
    if "modifiedBy" in dashboard:
        dashboard["modifiedBy"] = {"id": new_modifier, "type": "user"}
    return [
        ActualChange(
            dashboard_id=dashboard_id,
            dashboard_title=dashboard_title,
            change_type="creator_updated",
            old_value=f"{old_creator} / {old_modifier}",
            new_value=f"{new_creator} / {new_modifier}",
            object_type=update_info.object_type,
        )
    ]


def _sync_permissions(
    dashboard: dict,
    dashboard_id: str,
    dashboard_title: str,
    update_info: ObjectUpdate,
    skip_creators: bool,
    skip_individual_grantees: bool,
    skip_group_grantees: bool,
    permission_level: str,
    keep_existing_permissions: bool,
) -> list[ActualChange]:
    """Update permissions array to match Legacy intent."""
    permissions = dashboard.setdefault("permissions", [])
    desired_permissions = _build_desired_permissions(
        update_info,
        skip_creators,
        skip_individual_grantees,
        skip_group_grantees,
        permission_level,
    )
    changes: list[ActualChange] = []
    if not keep_existing_permissions:
        changes.extend(
            _remove_obsolete_permissions(
                permissions,
                desired_permissions,
                dashboard_id,
                dashboard_title,
                update_info,
                skip_creators,
                skip_individual_grantees,
                skip_group_grantees,
            )
        )
    changes.extend(
        _apply_desired_permissions(
            permissions,
            desired_permissions,
            dashboard_id,
            dashboard_title,
        )
    )
    if not permissions:
        logger.warning(
            "Dashboard '%s' (ID: %s) has NO permissions! It may be inaccessible to users.",
            dashboard_title,
            dashboard_id,
        )
    return changes


def _build_desired_permissions(
    update_info: ObjectUpdate,
    skip_creators: bool,
    skip_individual_grantees: bool,
    skip_group_grantees: bool,
    permission_level: str,
) -> dict[tuple[str, str], str]:
    """Create dictionary describing desired permission state."""
    desired: dict[tuple[str, str], str] = {}
    if not skip_creators and update_info.cloud_creator_id:
        desired[(update_info.cloud_creator_id, "user")] = "EDIT"
    if not skip_individual_grantees and update_info.grantee_user_ids:
        for user_id in update_info.grantee_user_ids:
            desired.setdefault((user_id, "user"), permission_level)
    if not skip_group_grantees and update_info.grantee_group_ids:
        for group_id in update_info.grantee_group_ids:
            desired[(group_id, "userGroup")] = permission_level
    return desired


def _remove_obsolete_permissions(
    permissions: list[dict],
    desired_permissions: dict[tuple[str, str], str],
    dashboard_id: str,
    dashboard_title: str,
    update_info: ObjectUpdate,
    skip_creators: bool,
    skip_individual_grantees: bool,
    skip_group_grantees: bool,
) -> list[ActualChange]:
    """Remove permissions not present in the desired mapping."""
    retained: list[dict] = []
    changes: list[ActualChange] = []
    for perm in permissions:
        assignee = perm.get("assignee", {})
        assignee_id = assignee.get("id", "")
        assignee_type = assignee.get("type", "")
        if not _should_manage_permission(
            assignee_type,
            assignee_id,
            update_info,
            skip_creators,
            skip_individual_grantees,
            skip_group_grantees,
        ):
            retained.append(perm)
            continue
        key = (assignee_id, assignee_type)
        if key in desired_permissions:
            retained.append(perm)
            continue
        changes.append(
            ActualChange(
                dashboard_id=dashboard_id,
                dashboard_title=dashboard_title,
                change_type="permission_removed",
                assignee_type=assignee_type,
                user_or_group_id=assignee_id,
                assignee_label=_assignee_label(assignee_type, assignee_id),
                old_permission=perm.get("name", ""),
            )
        )
    permissions[:] = retained
    return changes


def _apply_desired_permissions(
    permissions: list[dict],
    desired_permissions: dict[tuple[str, str], str],
    dashboard_id: str,
    dashboard_title: str,
) -> list[ActualChange]:
    """Ensure desired permissions exist and have correct level."""
    changes: list[ActualChange] = []
    current_map = {
        (perm.get("assignee", {}).get("id"), perm.get("assignee", {}).get("type")): perm
        for perm in permissions
    }
    for (assignee_id, assignee_type), desired_level in desired_permissions.items():
        perm = current_map.get((assignee_id, assignee_type))
        label = _assignee_label(assignee_type, assignee_id or "")
        if perm:
            current_level = perm.get("name")
            if current_level == desired_level:
                continue
            perm["name"] = desired_level
            changes.append(
                ActualChange(
                    dashboard_id=dashboard_id,
                    dashboard_title=dashboard_title,
                    change_type="permission_changed",
                    assignee_type=assignee_type or "",
                    user_or_group_id=assignee_id or "",
                    assignee_label=label,
                    old_permission=current_level or "",
                    new_permission=desired_level,
                )
            )
            continue
        permissions.append(
            {
                "assignee": {"id": assignee_id, "type": assignee_type},
                "name": desired_level,
            }
        )
        changes.append(
            ActualChange(
                dashboard_id=dashboard_id,
                dashboard_title=dashboard_title,
                change_type="permission_added",
                assignee_type=assignee_type,
                user_or_group_id=assignee_id,
                assignee_label=label,
                new_permission=desired_level,
            )
        )
    return changes


def _should_manage_permission(
    assignee_type: str,
    assignee_id: str,
    update_info: ObjectUpdate,
    skip_creators: bool,
    skip_individual_grantees: bool,
    skip_group_grantees: bool,
) -> bool:
    """Determine whether we should manage the provided permission entry."""
    if assignee_type == "user":
        if not skip_individual_grantees:
            return True
        return (
            not skip_creators
            and update_info.cloud_creator_id is not None
            and assignee_id == update_info.cloud_creator_id
        )
    if assignee_type == "userGroup":
        return not skip_group_grantees
    return False


def _assignee_label(assignee_type: str, identifier: str) -> str:
    """Return readable label for a permission assignee."""
    noun = "user" if assignee_type == "user" else "user group"
    value = identifier or "unknown"
    return f"{noun} '{value}'"


def validate_layout_structure(layout: dict) -> bool:
    """
    Validates that the layout has the expected structure.

    Args:
        layout: The workspace layout dictionary

    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(layout, dict):
        return False

    if "analytics" not in layout:
        return False

    analytics = layout.get("analytics", {})
    if not isinstance(analytics, dict):
        return False

    # Check if analyticalDashboards exists (it's ok if empty)
    if "analyticalDashboards" not in analytics:
        return False

    return True
