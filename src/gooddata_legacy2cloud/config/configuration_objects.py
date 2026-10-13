# (C) 2026 GoodData Corporation
"""
Configuration objects for the entry point migrations scripts.

These objects serve as an interface between the command line arguments and the
execution logic of the scripts.
"""

from typing import Any, Literal, Self, TypeAlias

from pydantic import Field

from gooddata_legacy2cloud.config.shared_configs import (
    BaseConfig,
    CommonConfig,
    ObjectFilterConfig,
    ObjectMigrationConfig,
    WorkspaceConfig,
)
from gooddata_legacy2cloud.constants import (
    DASHBOARD_MAPPING_FILE,
    INSIGHT_MAPPING_FILE,
    LDM_MAPPING_FILE,
    METRIC_MAPPING_FILE,
    PIXEL_PERFECT_DASHBOARD_MAPPING_FILE,
    REPORT_MAPPING_FILE,
    SCHEDULED_EXPORT_MAPPING_FILE,
)
from gooddata_legacy2cloud.helpers import set_output_files_prefix


class ColorPaletteConfig(BaseConfig):
    """Execution configuration for color palette migration"""

    workspace_config: WorkspaceConfig

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
        )


class DashboardPermissionsConfig(BaseConfig):
    """Config for dashboard permissions migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_filter_config: ObjectFilterConfig

    # Mapping arguments
    dashboard_mapping_file: list[str] = Field(
        default_factory=lambda: [DASHBOARD_MAPPING_FILE],
        description="Dashboard mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{DASHBOARD_MAPPING_FILE}]",
    )
    pp_dashboard_mapping_file: list[str] = Field(
        default_factory=lambda: [PIXEL_PERFECT_DASHBOARD_MAPPING_FILE],
        description="Pixel Perfect dashboard mappings file name(s). First file "
        + "is treated as default and also used for output, all files are used "
        + f"for input. Default: [{PIXEL_PERFECT_DASHBOARD_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description=f"Metric mappings file name(s). Default: [{METRIC_MAPPING_FILE}]",
    )
    insight_mapping_file: list[str] = Field(
        default_factory=lambda: [INSIGHT_MAPPING_FILE],
        description="Insight mappings file name(s). "
        + f"Default: [{INSIGHT_MAPPING_FILE}]",
    )

    # Custom migration arguments
    include_metrics: bool = Field(
        default=False,
        description="Also migrate creator/modifier of metrics",
    )
    include_insights: bool = Field(
        default=False,
        description="Also migrate creator/modifier of insights",
    )
    dump_layout: bool = Field(
        default=False,
        description="Save the layout JSON before and after modifications",
    )
    use_email: bool = Field(
        default=False,
        description="Use email field instead of login field when matching Legacy users",
    )
    skip_creators: bool = Field(
        default=False,
        description="Skip migrating creator permissions",
    )
    skip_individual_grantees: bool = Field(
        default=False,
        description="Skip migrating individual user grantee permissions",
    )
    skip_group_grantees: bool = Field(
        default=False,
        description="Skip migrating user group grantee permissions",
    )
    skip_kpi_dashboards: bool = Field(
        default=False,
        description="Skip migrating KPI dashboards",
    )
    skip_pp_dashboards: bool = Field(
        default=False,
        description="Skip migrating Pixel Perfect dashboards",
    )
    permission: Literal["VIEW", "SHARE", "EDIT"] = Field(
        default="EDIT",
        description="Permission level to assign to grantees (default: EDIT)",
    )
    keep_existing_permissions: bool = Field(
        default=False,
        description="Keep permissions not present in source instead of removing them",
    )
    print_user_mappings: bool = Field(
        default=False,
        description="Print detailed user mapping information for each Legacy user",
    )

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_filter_config=ObjectFilterConfig.model_validate(kwargs),
        )


class ScheduledExportConfig(BaseConfig):
    """Config for scheduled exports migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig

    # Mapping arguments
    ldm_mapping_file: list[str] = Field(
        default_factory=lambda: [LDM_MAPPING_FILE],
        description="LDM mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. "
        + f"Default: [{LDM_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description="Metric mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{METRIC_MAPPING_FILE}]",
    )
    insight_mapping_file: list[str] = Field(
        default_factory=lambda: [INSIGHT_MAPPING_FILE],
        description="Insight mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{INSIGHT_MAPPING_FILE}]",
    )
    dashboard_mapping_file: list[str] = Field(
        default_factory=lambda: [DASHBOARD_MAPPING_FILE],
        description="Dashboard mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{DASHBOARD_MAPPING_FILE}]",
    )
    scheduled_export_mapping_file: list[str] = Field(
        default_factory=lambda: [SCHEDULED_EXPORT_MAPPING_FILE],
        description="Scheduled export mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{SCHEDULED_EXPORT_MAPPING_FILE}]",
    )

    # Custom migration arguments
    exports_to_migrate: str | None = Field(
        default=None,
        description="Path to a file containing a list of scheduled export IDs to migrate. "
        + "If not provided, all scheduled exports will be migrated.",
    )

    def model_post_init(self, __context) -> None:
        validate_config(self)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
        )


class ReportConfig(BaseConfig):
    """Config for reports migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig
    object_filter_config: ObjectFilterConfig

    # Mapping arguments
    ldm_mapping_file: list[str] = Field(
        default_factory=lambda: [LDM_MAPPING_FILE],
        description="LDM mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. "
        + f"Default: [{LDM_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description="Metric mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{METRIC_MAPPING_FILE}]",
    )
    report_mapping_file: list[str] = Field(
        default_factory=lambda: [REPORT_MAPPING_FILE],
        description="Report mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{REPORT_MAPPING_FILE}]",
    )

    # Validation element lookup
    validation_element_lookup: bool = Field(
        default=False,
        description="Considers fetching of validation elements while searching "
        + "for attribute values",
    )
    element_values_prefetch: bool = Field(
        default=False,
        description="Prefetch element values in batches before processing. "
        + "Scans objects for element URIs and fetches their values using batch "
        + "API calls (up to 50 per request), storing them in cache for "
        + "efficient lookup during processing.",
    )

    # Report prefix
    report_prefix: str | None = Field(
        default=None,
        description="Override the default '[PP] ' prefix for migrated reports. "
        + "Use empty string to disable the prefix.",
    )
    keep_original_ids: bool = Field(
        default=False,
        description="Keep original Legacy identifiers as Cloud IDs instead of "
        + "deriving new IDs from the object title and Legacy identifier.",
    )

    def model_post_init(self, __context) -> None:
        validate_config(self)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
            object_filter_config=ObjectFilterConfig.model_validate(kwargs),
        )


class PixelPerfectDashboardConfig(BaseConfig):
    """Config for pixel perfect dashboard migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig
    object_filter_config: ObjectFilterConfig

    # Mapping arguments
    ldm_mapping_file: list[str] = Field(
        default_factory=lambda: [LDM_MAPPING_FILE],
        description="LDM mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{LDM_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description="Metric mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{METRIC_MAPPING_FILE}]",
    )
    insight_mapping_file: list[str] = Field(
        default_factory=lambda: [INSIGHT_MAPPING_FILE],
        description="Insight mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{INSIGHT_MAPPING_FILE}]",
    )
    report_mapping_file: list[str] = Field(
        default_factory=lambda: [REPORT_MAPPING_FILE],
        description="Report mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{REPORT_MAPPING_FILE}]",
    )

    # Validation element lookup
    validation_element_lookup: bool = Field(
        default=False,
        description="Considers fetching of validation elements while searching "
        + "for attribute values",
    )

    # Pixel Perfect Dashboard custom arguments
    pp_legacy_split_tabs: bool = Field(
        default=False,
        description="Legacy behavior: migrate each PP dashboard tab as a "
        + "separate KPI dashboard. By default, PP dashboards are migrated "
        + "one-to-one as a single tabbed KPI dashboard.",
    )
    keep_original_ids: bool = Field(
        default=False,
        description="Keep original Legacy identifiers as Cloud IDs instead of generating new ones.",
    )

    def model_post_init(self, __context) -> None:
        validate_config(self)
        if self.keep_original_ids and self.pp_legacy_split_tabs:
            raise ValueError(
                "`--keep-original-ids` cannot be used together with `--pp-legacy-split-tabs`. "
                "Split-tabs mode creates one Cloud dashboard per Legacy tab, which would cause "
                "ID collisions when keeping original IDs."
            )

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
            object_filter_config=ObjectFilterConfig.model_validate(kwargs),
        )


class DashboardConfig(BaseConfig):
    """Config for dashboards migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig
    object_filter_config: ObjectFilterConfig

    # Mapping arguments
    ldm_mapping_file: list[str] = Field(
        default_factory=lambda: [LDM_MAPPING_FILE],
        description="LDM mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{LDM_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description="Metric mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{METRIC_MAPPING_FILE}]",
    )
    insight_mapping_file: list[str] = Field(
        default_factory=lambda: [INSIGHT_MAPPING_FILE],
        description="Insight mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{INSIGHT_MAPPING_FILE}]",
    )
    dashboard_mapping_file: list[str] = Field(
        default_factory=lambda: [DASHBOARD_MAPPING_FILE],
        description="Dashboard mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{DASHBOARD_MAPPING_FILE}]",
    )

    # Validation element lookup
    validation_element_lookup: bool = Field(
        default=False,
        description="Considers fetching of validation elements while searching "
        + "for attribute values",
    )
    element_values_prefetch: bool = Field(
        default=False,
        description="Prefetch element values in batches before processing. "
        + "Scans objects for element URIs and fetches their values using batch "
        + "API calls (up to 50 per request), storing them in cache for efficient "
        + "lookup during processing.",
    )
    validation_element_lookup_with_metrics: bool = Field(
        default=False,
        description="Advanced element lookup using Legacy metrics and validation. "
        + "Automatically enables prefetching, then creates temporary Legacy metrics "
        + "containing unmapped elements. Running workspace validation populates "
        + "the cache with these elements. The temporary metrics are automatically "
        + "deleted afterward.",
    )
    keep_original_ids: bool = Field(
        default=False,
        description="Keep original Legacy identifiers as Cloud IDs instead of generating new ones.",
    )

    # Custom dashboard arguments
    dashboard_type: str = Field(
        default="analyticalDashboard",
        description="Type of the dashboard to migrate. Default is 'analyticalDashboard'.",
    )

    def model_post_init(self, __context) -> None:
        validate_config(self)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
            object_filter_config=ObjectFilterConfig.model_validate(kwargs),
        )


class InsightConfig(BaseConfig):
    """Config for insights migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig
    object_filter_config: ObjectFilterConfig

    # Mapping arguments
    ldm_mapping_file: list[str] = Field(
        default_factory=lambda: [LDM_MAPPING_FILE],
        description="LDM mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{LDM_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description="Metric mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{METRIC_MAPPING_FILE}]",
    )
    insight_mapping_file: list[str] = Field(
        default_factory=lambda: [INSIGHT_MAPPING_FILE],
        description="Insight mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{INSIGHT_MAPPING_FILE}]",
    )

    # Validation element lookup
    validation_element_lookup: bool = Field(
        default=False,
        description="Considers fetching of validation elements while searching "
        + "for attribute values.",
    )
    element_values_prefetch: bool = Field(
        default=False,
        description="Prefetch element values in batches before processing. "
        + "Scans objects for element URIs and fetches their values using batch "
        + "API calls (up to 50 per request), storing them in cache for efficient "
        + "lookup during processing.",
    )
    validation_element_lookup_with_metrics: bool = Field(
        default=False,
        description="Advanced element lookup using Legacy metrics and validation. "
        + "Automatically enables prefetching, then creates temporary Legacy metrics "
        + "containing unmapped elements. Running workspace validation populates "
        + "the cache with these elements. The temporary metrics are automatically deleted afterward.",
    )
    keep_original_ids: bool = Field(
        default=False,
        description="Keep original Legacy identifiers as Cloud IDs instead of generating new ones.",
    )

    def model_post_init(self, __context) -> None:
        validate_config(self)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
            object_filter_config=ObjectFilterConfig.model_validate(kwargs),
        )


class MetricConfig(BaseConfig):
    """Config for metrics migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig
    object_filter_config: ObjectFilterConfig

    # Mapping arguments
    ldm_mapping_file: list[str] = Field(
        default_factory=lambda: [LDM_MAPPING_FILE],
        description="LDM mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{LDM_MAPPING_FILE}]",
    )
    metric_mapping_file: list[str] = Field(
        default_factory=lambda: [METRIC_MAPPING_FILE],
        description="Metric mappings file name(s). First file is treated as "
        + "default and also used for output, all files are used for input. "
        + f"Default: [{METRIC_MAPPING_FILE}]",
    )

    # Validation element lookup
    validation_element_lookup: bool = Field(
        default=False,
        description="Considers fetching of validation elements while searching "
        + "for attribute values",
    )
    element_values_prefetch: bool = Field(
        default=False,
        description="Prefetch element values in batches before processing. "
        + "Scans objects for element URIs and fetches their values using batch "
        + "API calls (up to 50 per request), storing them in cache for efficient "
        + "lookup during processing.",
    )

    # Metric custom arguments
    keep_original_ids: bool = Field(
        default=False,
        description="It will keep the original ids of the metrics.",
    )
    ignore_folders: bool = Field(
        default=False,
        description="Legacy folders are not migrated to Cloud tags.",
    )

    def model_post_init(self, __context) -> None:
        validate_config(self)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
            object_filter_config=ObjectFilterConfig.model_validate(kwargs),
        )


class LDMConfig(BaseConfig):
    """Config for LDM migration."""

    workspace_config: WorkspaceConfig
    common_config: CommonConfig
    object_migration_config: ObjectMigrationConfig

    # Custom LDM config
    ignore_folders: bool = Field(
        default=False,
        description="Legacy folders are not migrated to Cloud tags.",
    )
    ignore_explicit_mapping: bool = Field(
        default=False,
        description="Explicit mapping is not used even when it exists.",
    )

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(
            **kwargs,
            workspace_config=WorkspaceConfig.model_validate(kwargs),
            common_config=CommonConfig.model_validate(kwargs),
            object_migration_config=ObjectMigrationConfig.model_validate(kwargs),
        )


class WebCompareConfig(BaseConfig):
    """Config for web compare migration."""

    log_dir: str = Field(
        default=".",
        description="Path to a directory containing migration log files (*_logs.log). Defaults to current directory.",
    )
    output_dir: str = Field(
        default="web_compare",
        description="Directory to write HTML output to (default: compare_web)",
    )
    skip_inherited: bool = Field(
        default=False,
        description="Skip including unprefixed objects in prefixed outputs with 'inherited' status",
    )

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Self:
        return cls(**kwargs)


ModelToValidate: TypeAlias = (
    MetricConfig
    | InsightConfig
    | DashboardConfig
    | ReportConfig
    | PixelPerfectDashboardConfig
    | ScheduledExportConfig
)


def is_client_prefix_used(common_config: CommonConfig) -> bool:
    """Returns True if client prefix is used, False otherwise."""
    return (common_config.client_prefix is not None) and (
        common_config.client_prefix != ""
    )


def is_mapping_params_used(config: ModelToValidate) -> bool:
    """Returns True if any mapping file parameter is used with non-default values, False otherwise."""
    for param in [
        "ldm_mapping_file",
        "metric_mapping_file",
        "insight_mapping_file",
        "dashboard_mapping_file",
        "report_mapping_file",
    ]:
        # Skip checking if the parameter doesn't exist in args
        if not hasattr(config, param):
            continue

        # If parameter exists and it's not equal to its default value, then it's used
        param_value = getattr(config, param)

        # We can't use globals() here because we're not in the same module
        # So we'll manually check defaults
        default_value = None
        if param == "ldm_mapping_file":
            default_value = [LDM_MAPPING_FILE]
        elif param == "metric_mapping_file":
            default_value = [METRIC_MAPPING_FILE]
        elif param == "insight_mapping_file":
            default_value = [INSIGHT_MAPPING_FILE]
        elif param == "dashboard_mapping_file":
            default_value = [DASHBOARD_MAPPING_FILE]
        elif param == "report_mapping_file":
            default_value = [REPORT_MAPPING_FILE]

        if param_value != default_value:
            return True

    return False


def validate_config(config: ModelToValidate):
    """
    Validates the config for conflicts.

    Args:
        config: The config to validate.

    Raises:
        ValueError: If there are conflicts in the config.
    """
    # Check if client prefix is used alongside any mapping parameters
    client_prefix_used = is_client_prefix_used(config.common_config)
    mapping_params_used = is_mapping_params_used(config)

    # Check if any mapping file parameters are used with non-default values
    if client_prefix_used and mapping_params_used:
        raise ValueError(
            "`client-prefix` cannot be used together with explicit mapping file parameters.\n"
            "Please use either `client-prefix` OR the specific mapping file parameters."
        )

    # When using client_prefix, require workspace parameters to be specified
    # This prevents accidentally using master workspaces from the .env file
    if client_prefix_used:
        if (
            not config.workspace_config.legacy_ws
            or not config.workspace_config.cloud_ws
        ):
            raise ValueError(
                "`client-prefix` requires both `legacy-ws` and `cloud-ws` to be specified.\n"
                "This ensures you're migrating between the correct client workspaces, not the master workspaces in .env."
            )

    # If client prefix is used, set output_files_prefix to the same value
    if client_prefix_used:
        config.common_config.output_files_prefix = config.common_config.client_prefix
        set_output_files_prefix(config.common_config.client_prefix)

        # Always enable parent workspace check when using client prefix
        config.common_config.check_parent_workspace = True

        if not isinstance(config, ScheduledExportConfig):
            # Set the default behavior to filter out objects already in the default mapping files
            # when using --client-prefix (for parent/child migration scenarios)
            # NOTE: Scheduled exports do not have the object filter config
            if config.object_filter_config.without_mapped_objects is None:
                config.object_filter_config.without_mapped_objects = "default_only"
