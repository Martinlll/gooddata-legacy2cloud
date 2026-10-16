# (C) 2026 GoodData Corporation
"""Data classes for dashboard permissions migration."""

from dataclasses import dataclass, field

from gooddata_legacy2cloud.backends.cloud.client import CloudClient
from gooddata_legacy2cloud.backends.legacy.client import LegacyClient
from gooddata_legacy2cloud.id_mappings import IdMappings


@dataclass
class ActualChange:
    """
    Tracks an actual change made to a dashboard during layout update.

    Attributes:
        dashboard_id: Cloud dashboard ID
        dashboard_title: Dashboard title
        change_type: Change category
        assignee_type: 'user' or 'userGroup' when applicable
        user_or_group_id: Cloud identifier of the assignee
        assignee_label: Human readable label (email, login, or group name)
        old_value: Previous creator identifier
        new_value: New creator identifier
        old_permission: Previous permission name
        new_permission: New permission name
    """

    dashboard_id: str
    dashboard_title: str
    change_type: str
    assignee_type: str = field(default="")
    user_or_group_id: str = field(default="")
    assignee_label: str = field(default="")
    old_value: str = field(default="")
    new_value: str = field(default="")
    old_permission: str = field(default="")
    new_permission: str = field(default="")
    object_type: str = field(default="dashboard")


@dataclass(frozen=True)
class DashboardPermissionContext:
    """
    Context for dashboard permissions migration operations.

    Attributes:
        legacy_client: LegacyClient
        cloud_client: CloudClient
        dashboard_mappings: ID mappings from Legacy to Cloud
        use_email: Whether to use email instead of login for user matching
        skip_creators: Whether to skip migrating creator permissions
        skip_individual_grantees: Whether to skip migrating individual user grantees
        skip_group_grantees: Whether to skip migrating user group grantees
        permission_level: Permission level to assign (VIEW, SHARE, or EDIT)
        print_user_mappings: Whether to print detailed user mapping information
        client_prefix: Optional client prefix for file naming
    """

    legacy_client: LegacyClient
    cloud_client: CloudClient
    dashboard_mappings: IdMappings
    use_email: bool = field(default=False)
    skip_creators: bool = field(default=False)
    skip_individual_grantees: bool = field(default=False)
    skip_group_grantees: bool = field(default=False)
    permission_level: str = field(default="EDIT")
    keep_existing_permissions: bool = field(default=False)
    print_user_mappings: bool = field(default=False)
    client_prefix: str | None = field(default=None)
    metric_mappings: IdMappings | None = field(default=None)
    insight_mappings: IdMappings | None = field(default=None)
