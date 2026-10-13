# (C) 2025 GoodData Corporation
"""Utilities for formatting dashboard permission change messages."""

from gooddata_legacy2cloud.dashboard_permissions.data_classes import ActualChange


def format_change_line(change: ActualChange) -> str:
    """
    Convert an ActualChange into the canonical log/console string.

    Args:
        change: Change data captured during layout update.

    Returns:
        Formatted string containing dashboard, action, and target context.
    """

    prefix = (
        f"  {change.object_type.capitalize()}: '{change.dashboard_title}' "
        f"(ID: {change.dashboard_id}) - "
    )

    if change.change_type == "creator_updated":
        return (
            f"{prefix}Changed creator / modifier from '{change.old_value}' "
            f"to '{change.new_value}'"
        )

    if change.change_type == "permission_removed":
        return (
            f"{prefix}Removing {change.old_permission or 'permission'} "
            f"for {change.assignee_label}"
        )

    if change.change_type == "permission_changed":
        return (
            f"{prefix}Changing permission for {change.assignee_label} "
            f"from {change.old_permission} to {change.new_permission}"
        )

    if change.change_type == "permission_added":
        return (
            f"{prefix}Adding {change.new_permission or 'permission'} "
            f"for {change.assignee_label}"
        )

    return prefix.rstrip(" -")
