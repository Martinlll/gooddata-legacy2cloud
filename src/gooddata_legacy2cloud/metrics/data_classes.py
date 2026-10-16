# (C) 2026 GoodData Corporation

from dataclasses import dataclass, field

from gooddata_legacy2cloud.backends.cloud.client import CloudClient
from gooddata_legacy2cloud.backends.legacy.client import LegacyClient
from gooddata_legacy2cloud.id_mappings import IdMappings
from gooddata_legacy2cloud.output_writer import OutputWriter


@dataclass(frozen=True)
class MetricContext:
    legacy_client: LegacyClient
    cloud_client: CloudClient
    ldm_mappings: IdMappings
    mapping_logger: OutputWriter
    keep_original_ids: bool  # keep original ids of the metrics
    ignore_folders: bool  # ignore folders
    suppress_warnings: bool = field(
        default=False
    )  # suppress migration warnings from objects
    client_prefix: str | None = field(default=None)
    metric_mappings: IdMappings | None = field(default=None)
