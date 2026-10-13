# (C) 2026 GoodData Corporation
"""
This module contains utilities for argument parsing used by the main scripts.
"""

import argparse

from gooddata_legacy2cloud.constants import (
    DASHBOARD_MAPPING_FILE,
    INSIGHT_MAPPING_FILE,
    LDM_MAPPING_FILE,
    METRIC_MAPPING_FILE,
    PIXEL_PERFECT_DASHBOARD_MAPPING_FILE,
    REPORT_MAPPING_FILE,
    SCHEDULED_EXPORT_MAPPING_FILE,
)


def comma_separated_values(value: str) -> list[str] | None:
    if value is None:
        return None
    return [x.strip() for x in value.split(",")]


def add_legacy_ws_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--legacy-ws",
        dest="legacy_ws",
        help="Source Legacy workspace ID. Overrides LEGACY_WS from the .env file if exists.",
        default=None,
    )


def add_cloud_ws_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cloud-ws",
        dest="cloud_ws",
        help="Target Cloud workspace ID. Overrides CLOUD_WS from the .env file if exists.",
        default=None,
    )


def add_env_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", type=str, help="Path to the .env file", default=".env")


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Adds common arguments to the parser that are used by all migration scripts."""
    parser.add_argument(
        "--skip-deploy",
        action="store_const",
        const=True,
        dest="skip_deploy",
        default=False,
        help="Skips PUT request to Cloud. Useful for testing purposes.",
    )

    parser.add_argument(
        "--output-files-prefix",
        dest="output_files_prefix",
        help="Prefix to add to all output files. Default is empty (no prefix).",
        default="",
    )

    parser.add_argument(
        "--client-prefix",
        dest="client_prefix",
        help="Client prefix to automatically set output-files-prefix and include "
        + "client-specific mapping files.",
        default="",
    )

    add_env_argument(parser)

    # Add workspace override arguments
    add_legacy_ws_argument(parser)
    add_cloud_ws_argument(parser)

    parser.add_argument(
        "--check-parent-workspace",
        action="store_const",
        const=True,
        dest="check_parent_workspace",
        default=False,
        help="Check if the target Cloud workspace has a parent workspace. "
        + "Required for client workspace migrations.",
    )


def add_object_migration_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds arguments specific to object migration/creation scripts:
    - Dump arguments (--dump-legacy, --dump-cloud)
    - Object update control (--overwrite-existing)
    - Warning suppression (--suppress-migration-warnings)

    These arguments are used by scripts that create/migrate individual objects
    (metrics, insights, dashboards, reports, scheduled exports, LDM).
    Not needed by scripts that only update existing objects (dashboard permissions).
    """
    parser.add_argument(
        "--dump-legacy",
        action="store_const",
        const=True,
        dest="dump_legacy",
        default=False,
        help="Dumps Legacy objects to a JSON file.",
    )

    parser.add_argument(
        "--dump-cloud",
        action="store_const",
        const=True,
        dest="dump_cloud",
        default=False,
        help="Dumps Cloud objects to a JSON file.",
    )

    parser.add_argument(
        "--overwrite-existing",
        action="store_const",
        const=True,
        dest="overwrite_existing",
        default=False,
        help="Overwrites existing objects in Cloud instead of skipping them during migration.",
    )

    parser.add_argument(
        "--suppress-migration-warnings",
        action="store_const",
        const=True,
        dest="suppress_migration_warnings",
        default=False,
        help="Suppress migration warnings from being added to object titles and "
        + "descriptions. Warnings will still be printed to console.",
    )


def add_ldm_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds LDM mapping file arguments to the parser.
    """
    parser.add_argument(
        "--ldm-mapping-file",
        dest="ldm_mapping_file",
        help="LDM mappings file name(s). First file is treated as default and "
        + "also used for output, all files are used for input. Comma-separated list. "
        + f"Default: {LDM_MAPPING_FILE}",
        default=[LDM_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_metric_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds metric mapping file arguments to the parser.
    """
    parser.add_argument(
        "--metric-mapping-file",
        dest="metric_mapping_file",
        help="Metric mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. Comma-separated "
        + f"list. Default: {METRIC_MAPPING_FILE}",
        default=[METRIC_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_insight_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds insight mapping file arguments to the parser.
    """
    parser.add_argument(
        "--insight-mapping-file",
        dest="insight_mapping_file",
        help="Insight mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. Comma-separated "
        + f"list. Default: {INSIGHT_MAPPING_FILE}",
        default=[INSIGHT_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_dashboard_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds dashboard mapping file arguments to the parser.
    """
    parser.add_argument(
        "--dashboard-mapping-file",
        dest="dashboard_mapping_file",
        help="Dashboard mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. Comma-separated "
        + f"list. Default: {DASHBOARD_MAPPING_FILE}",
        default=[DASHBOARD_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_pp_dashboard_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds Pixel Perfect dashboard mapping file arguments to the parser.
    """
    parser.add_argument(
        "--pp-dashboard-mapping-file",
        dest="pp_dashboard_mapping_file",
        help="Pixel Perfect dashboard mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. Comma-separated "
        + f"list. Default: {PIXEL_PERFECT_DASHBOARD_MAPPING_FILE}",
        default=[PIXEL_PERFECT_DASHBOARD_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_report_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds report mapping file arguments to the parser.
    """
    parser.add_argument(
        "--report-mapping-file",
        dest="report_mapping_file",
        help="Report mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. Comma-separated "
        + f"list. Default: {REPORT_MAPPING_FILE}",
        default=[REPORT_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_scheduled_export_mapping_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds scheduled export mapping file arguments to the parser.
    """
    parser.add_argument(
        "--scheduled-export-mapping-file",
        dest="scheduled_export_mapping_file",
        help="Scheduled export mappings file name(s). First file is treated as default "
        + "and also used for output, all files are used for input. Comma-separated "
        + f"list. Default: {SCHEDULED_EXPORT_MAPPING_FILE}",
        default=[SCHEDULED_EXPORT_MAPPING_FILE],
        type=comma_separated_values,
    )


def add_object_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds common object filtering arguments to the parser.
    These are used to filter which objects are migrated.
    """
    parser.add_argument(
        "--with-tags",
        dest="with_tags",
        help="Only migrate objects with at least one of the specified tags "
        + "(comma-separated)",
        default=None,
        type=comma_separated_values,
    )

    parser.add_argument(
        "--without-tags",
        dest="without_tags",
        help="Only migrate objects that don't have any of the specified tags "
        + "(comma-separated)",
        default=None,
        type=comma_separated_values,
    )

    parser.add_argument(
        "--with-creator-profiles",
        dest="with_creator_profiles",
        help="Only migrate objects created by one of the specified Legacy user profile IDs "
        + "(comma-separated, without /gdc/account/profile/ prefix)",
        default=None,
        type=comma_separated_values,
    )

    parser.add_argument(
        "--without-creator-profiles",
        dest="without_creator_profiles",
        help="Only migrate objects NOT created by any of the specified Legacy user profile IDs "
        + "(comma-separated, without /gdc/account/profile/ prefix)",
        default=None,
        type=comma_separated_values,
    )

    # Create a mutually exclusive group for locked flag filtering parameters
    locked_flag_group = parser.add_mutually_exclusive_group()

    locked_flag_group.add_argument(
        "--with-locked-flag",
        action="store_const",
        const=True,
        dest="with_locked_flag",
        default=False,
        help="Only migrate objects that have locked=1 flag in their metadata",
    )

    locked_flag_group.add_argument(
        "--without-locked-flag",
        action="store_const",
        const=True,
        dest="without_locked_flag",
        default=False,
        help="Only migrate objects that have locked=0 or no locked flag in their metadata",
    )

    # Add filter for objects based on mapping files
    parser.add_argument(
        "--without-mapped-objects",
        dest="without_mapped_objects",
        nargs="?",
        const="all",  # Default value when flag is present but no value given
        default=None,  # Default value when flag is absent
        choices=["default_only", "all"],
        help="Filter out objects present in mapping files. When used without "
        + "value, filters objects in ANY mapping file. With 'default_only', only "
        + "checks the default mapping file.",
    )

    # Create a mutually exclusive group for object filtering parameters
    filter_group = parser.add_mutually_exclusive_group()

    filter_group.add_argument(
        "--only-object-ids",
        dest="only_object_ids",
        help="Only migrate specific objects by their IDs (comma-separated integers)",
        default=None,
        type=comma_separated_values,
    )

    filter_group.add_argument(
        "--only-object-ids-with-dependencies",
        dest="only_object_ids_with_dependencies",
        help="Only migrate specific objects by their IDs (comma-separated integers) "
        + "and include their dependencies",
        default=None,
        type=comma_separated_values,
    )

    filter_group.add_argument(
        "--only-identifiers",
        dest="only_identifiers",
        help="Only migrate specific objects by their alphanumeric identifiers "
        + "(comma-separated)",
        default=None,
        type=comma_separated_values,
    )

    filter_group.add_argument(
        "--only-identifiers-with-dependencies",
        dest="only_identifiers_with_dependencies",
        help="Only migrate specific objects by their alphanumeric identifiers "
        + "(comma-separated) and include their dependencies",
        default=None,
        type=comma_separated_values,
    )


def add_validation_element_lookup_argument(parser: argparse.ArgumentParser) -> None:
    """
    Adds validation element lookup argument to the parser.
    """
    parser.add_argument(
        "--validation-element-lookup",
        action="store_const",
        const=True,
        dest="validation_element_lookup",
        default=False,
        help="Considers fetching of validation elements while searching for "
        + "attribute values",
    )


def add_pp_dashboard_arguments(parser: argparse.ArgumentParser) -> None:
    """Adds Pixel Perfect dashboard-specific arguments."""
    parser.add_argument(
        "--pp-legacy-split-tabs",
        action="store_const",
        const=True,
        dest="pp_legacy_split_tabs",
        default=False,
        help=(
            "Legacy behavior: migrate each PP dashboard tab as a separate KPI dashboard. "
            "By default, PP dashboards are migrated one-to-one as a single tabbed KPI dashboard."
        ),
    )


def add_element_values_prefetch_argument(parser: argparse.ArgumentParser) -> None:
    """
    Adds element values prefetch argument to the parser.
    """
    parser.add_argument(
        "--element-values-prefetch",
        action="store_const",
        const=True,
        dest="element_values_prefetch",
        default=False,
        help="Prefetch element values in batches before processing. Scans objects for "
        + "element URIs and fetches their values using batch API calls (up to 50 per "
        + "request), storing them in cache for efficient lookup during processing.",
    )


def add_validation_element_lookup_with_metrics_argument(
    parser: argparse.ArgumentParser,
) -> None:
    """
    Adds validation element lookup with metrics argument to the parser.
    """
    parser.add_argument(
        "--validation-element-lookup-with-metrics",
        action="store_const",
        const=True,
        dest="validation_element_lookup_with_metrics",
        default=False,
        help="Advanced element lookup using Legacy metrics and validation. Automatically "
        + "enables prefetching, then creates temporary Legacy metrics containing "
        + "unmapped elements. Running workspace validation populates the cache "
        + "with these elements. The temporary metrics are automatically deleted afterward.",
    )


def add_keep_original_ids_argument(parser: argparse.ArgumentParser) -> None:
    """
    Adds keep-original-ids argument to the parser.
    """
    parser.add_argument(
        "--keep-original-ids",
        action="store_const",
        const=True,
        dest="keep_original_ids",
        default=False,
        help="Keep the original Legacy identifiers as Cloud IDs instead of "
        + "deriving new IDs from the object title and Legacy identifier.",
    )


def add_cleanup_target_env_argument(
    parser: argparse.ArgumentParser, object_type: str = "objects"
) -> None:
    parser.add_argument(
        "--cleanup-target-env",
        action="store_const",
        const=True,
        dest="cleanup_target_env",
        default=False,
        help="Prior to the migration, all pre-existing "
        + f"{object_type} will be "
        + "deleted from the target environment.",
    )


def parse_color_palette_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate color palette")
    add_legacy_ws_argument(parser)
    add_cloud_ws_argument(parser)
    add_env_argument(parser)

    args = parser.parse_args()
    return args


def parse_scheduled_export_cli_args() -> argparse.Namespace:
    # Create argument parses
    parser = argparse.ArgumentParser(description="Script inputs")

    # Add arguments
    add_common_arguments(parser)
    add_object_migration_arguments(parser)
    add_ldm_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_insight_mapping_arguments(parser)
    add_dashboard_mapping_arguments(parser)
    add_scheduled_export_mapping_arguments(parser)
    add_cleanup_target_env_argument(parser, object_type="scheduled exports")

    parser.add_argument(
        "--exports-to-migrate",
        dest="exports_to_migrate",
        help="Path to a file containing a list of scheduled export IDs to migrate. "
        + "If not provided, all scheduled exports will be migrated.",
        required=False,
        default=None,
    )

    # Parse arguments
    args = parser.parse_args()

    return args


def parse_report_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Script inputs")
    add_common_arguments(parser)
    add_object_migration_arguments(parser)
    add_object_filter_arguments(parser)
    add_ldm_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_report_mapping_arguments(parser)
    add_validation_element_lookup_argument(parser)
    add_element_values_prefetch_argument(parser)
    add_cleanup_target_env_argument(parser, object_type="reports")
    add_keep_original_ids_argument(parser)

    parser.add_argument(
        "--report-prefix",
        dest="report_prefix",
        default=None,
        help="Override the default '[PP] ' prefix for migrated reports. Use empty "
        + "string to disable the prefix.",
    )

    args = parser.parse_args()

    return args


def parse_pixel_perfect_dashboard_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Script inputs")

    # Parse arguments
    add_common_arguments(parser)
    add_object_migration_arguments(parser)
    add_cleanup_target_env_argument(parser)
    add_object_filter_arguments(parser)
    add_ldm_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_report_mapping_arguments(parser)
    add_insight_mapping_arguments(parser)
    add_validation_element_lookup_argument(parser)
    add_pp_dashboard_arguments(parser)
    add_keep_original_ids_argument(parser)

    args = parser.parse_args()
    return args


def parse_metric_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Script inputs")
    add_common_arguments(parser)
    add_object_migration_arguments(parser)
    add_object_filter_arguments(parser)
    add_ldm_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_validation_element_lookup_argument(parser)
    add_element_values_prefetch_argument(parser)
    add_cleanup_target_env_argument(parser, object_type="metrics")

    add_keep_original_ids_argument(parser)

    parser.add_argument(
        "--ignore-folders",
        action="store_const",
        const=True,
        dest="ignore_folders",
        default=False,
        help="Legacy folders are not migrated to Cloud tags.",
    )

    args = parser.parse_args()
    return args


def parse_ldm_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Script inputs")

    add_common_arguments(parser)
    add_object_migration_arguments(parser)

    parser.add_argument(
        "--ignore-folders",
        action="store_const",
        const=True,
        dest="ignore_folders",
        default=False,
        help="Legacy folders are not migrated to Cloud tags.",
    )

    parser.add_argument(
        "--ignore-explicit-mapping",
        action="store_const",
        const=True,
        dest="ignore_explicit_mapping",
        default=False,
        help="Explicit mapping is not used even when it exists.",
    )

    args = parser.parse_args()
    return args


def parse_insight_cli_args() -> argparse.Namespace:
    # Create argument parser
    parser = argparse.ArgumentParser(description="Script inputs")

    # Parse arguments
    add_common_arguments(parser)
    add_object_migration_arguments(parser)
    add_object_filter_arguments(parser)
    add_ldm_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_insight_mapping_arguments(parser)
    add_validation_element_lookup_argument(parser)
    add_element_values_prefetch_argument(parser)
    add_validation_element_lookup_with_metrics_argument(parser)
    add_keep_original_ids_argument(parser)
    add_cleanup_target_env_argument(parser, object_type="insights")

    args = parser.parse_args()
    return args


def parse_dashboard_cli_args() -> argparse.Namespace:
    # Create argument parser
    parser = argparse.ArgumentParser(description="Script inputs")

    add_common_arguments(parser)
    add_object_migration_arguments(parser)
    add_object_filter_arguments(parser)
    add_ldm_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_insight_mapping_arguments(parser)
    add_dashboard_mapping_arguments(parser)
    add_validation_element_lookup_argument(parser)
    add_element_values_prefetch_argument(parser)
    add_validation_element_lookup_with_metrics_argument(parser)
    add_keep_original_ids_argument(parser)
    add_cleanup_target_env_argument(parser, object_type="dashboards")

    parser.add_argument(
        "--dashboard-type",
        dest="dashboard_type",
        default="analyticalDashboard",
        help="Type of the dashboard to migrate. Default is 'analyticalDashboard'.",
    )

    args = parser.parse_args()

    return args


def parse_dashboard_permission_cli_args() -> argparse.Namespace:
    """Create and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate dashboard permissions and creator information"
    )
    add_common_arguments(parser)
    add_object_filter_arguments(parser)
    add_dashboard_mapping_arguments(parser)
    add_pp_dashboard_mapping_arguments(parser)
    add_metric_mapping_arguments(parser)
    add_insight_mapping_arguments(parser)
    parser.add_argument(
        "--include-metrics",
        action="store_true",
        help="Also migrate creator/modifier (author/contributor) of metrics",
    )
    parser.add_argument(
        "--include-insights",
        action="store_true",
        help="Also migrate creator/modifier (author/contributor) of insights",
    )
    parser.add_argument(
        "--dump-layout",
        action="store_true",
        help="Save the layout JSON before and after modifications",
    )
    parser.add_argument(
        "--use-email",
        action="store_true",
        help="Use email field instead of login field when matching Legacy users",
    )
    parser.add_argument(
        "--skip-creators",
        action="store_true",
        help="Skip migrating creator permissions",
    )
    parser.add_argument(
        "--skip-individual-grantees",
        action="store_true",
        help="Skip migrating individual user grantee permissions",
    )
    parser.add_argument(
        "--skip-group-grantees",
        action="store_true",
        help="Skip migrating user group grantee permissions",
    )
    parser.add_argument(
        "--skip-kpi-dashboards",
        action="store_true",
        help="Skip migrating KPI dashboards",
    )
    parser.add_argument(
        "--skip-pp-dashboards",
        action="store_true",
        help="Skip migrating Pixel Perfect dashboards",
    )
    parser.add_argument(
        "--permission",
        choices=["VIEW", "SHARE", "EDIT"],
        default="EDIT",
        help="Permission level to assign to grantees (default: EDIT)",
    )
    parser.add_argument(
        "--keep-existing-permissions",
        action="store_true",
        help="Keep permissions not present in source instead of removing them",
    )
    parser.add_argument(
        "--print-user-mappings",
        action="store_true",
        help="Print detailed user mapping information for each Legacy user",
    )
    args = parser.parse_args()

    return args


def parse_web_compare_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate web comparison HTML from migration log files"
    )

    # Only keep env for loading defaults from a specific .env file
    parser.add_argument(
        "--env",
        help="Environment to use. If not provided, the script will use the environment variables from .env",
    )

    # Only keep log directory parameter
    parser.add_argument(
        "--log-dir",
        help="Path to a directory containing migration log files (*_logs.log). Defaults to current directory.",
    )

    parser.add_argument(
        "--output-dir",
        default="web_compare",
        help="Directory to write HTML output to (default: compare_web)",
    )

    parser.add_argument(
        "--skip-inherited",
        action="store_true",
        default=False,
        help="Skip including unprefixed objects in prefixed outputs with 'inherited' status",
    )

    return parser.parse_args()
