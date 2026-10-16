# (C) 2026 GoodData Corporation
"""
This module contains helper functions used throughout the application.
"""

import json
import logging
import os
import re
import threading
import unicodedata
from time import time
from typing import Any

import attrs

from gooddata_legacy2cloud.backends.legacy.client import LegacyClient

logger = logging.getLogger("migration")

DASHBOARD_SPECIFIC_INSIGHT_PREFIX = "kpimigrationinsight"
REPORT_INSIGHT_PREFIX = "ppmigr"
PP_DASHBOARD_PREFIX = "ppdash"
PP_INSIGHT_PREFIX = "ppkpinsight"
PP_FILTER_CONTEXT_PREFIX = "ppctx"

# Global output files prefix, set by the command line argument
OUTPUT_FILES_PREFIX = ""


def set_output_files_prefix(prefix):
    """Sets the global output files prefix."""
    # TODO: let's tie this to config objects instead of relying on global variable
    global OUTPUT_FILES_PREFIX
    OUTPUT_FILES_PREFIX = prefix


def prefix_filename(filename):
    """
    Adds the global prefix to the filename.
    If the filename is a path, the prefix is added to the basename only.
    """
    if not OUTPUT_FILES_PREFIX:
        return filename

    # For paths like "dir/filename.csv", we need to add prefix only to the basename
    path, basename = os.path.split(filename)
    prefixed_basename = f"{OUTPUT_FILES_PREFIX}{basename}"

    # If there's a path, join it with the prefixed basename
    if path:
        return os.path.join(path, prefixed_basename)

    return prefixed_basename


def ensure_directory_exists(filename):
    """Ensures the parent directory of a file exists."""
    parent_dir = os.path.split(filename)[0]
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def get_json_content_from_file(filename: str):
    """Reads a JSON file and returns its content."""
    with open(filename, "r", encoding="utf-8") as f:
        model = json.load(f)
        return model


def write_content_to_file(filename: str, content: str):
    """Writes content to a file."""
    prefixed_filename = filename
    try:
        prefixed_filename = prefix_filename(filename)
        ensure_directory_exists(prefixed_filename)
        with open(prefixed_filename, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logger.error("Cannot create file for given path %s: %s", prefixed_filename, e)


def append_content_to_file(filename: str, content: str):
    """Appends content to a file."""
    prefixed_filename = filename
    try:
        prefixed_filename = prefix_filename(filename)
        ensure_directory_exists(prefixed_filename)
        with open(prefixed_filename, "a", encoding="utf-8") as f:
            f.write(content)
            f.write("\n")
    except Exception as e:
        logger.error("Cannot append to file %s: %s", prefixed_filename, e)


def text2identifier(text: str) -> str:
    """Converts a string to an identifier."""
    adjustedText = text.replace("#", "nr").replace("%", "pct")

    return (
        re.sub("[^A-Za-z0-9_ ]+", "", adjustedText)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def dashboard_specific_insight_id(text, dashboard_id=None):
    """
    Generates an ID for dashboard-specific insights.
    If dashboard_id is provided, it's included in the ID to make it unique across dashboards.
    """
    base_id = text2identifier(text)
    if dashboard_id:
        return f"{DASHBOARD_SPECIFIC_INSIGHT_PREFIX}_{dashboard_id}_{base_id}"
    return f"{DASHBOARD_SPECIFIC_INSIGHT_PREFIX}_{base_id}"


def print_json(json_object):
    """Logs a JSON object."""
    logger.info(json.dumps(json_object, indent=4))


def get_obj_id_from_link(self, link):
    match = re.search(r".*/obj/(\d+)", link)
    if match:
        return match.group(1)

    raise ValueError(f"Invalid link format. {link}")


def get_object_list(input):
    """
    Returns a list of objects that are present in the input string.
    """
    # The pattern to search for
    pattern = r"\[([^]]+)\]"

    # Find all matches
    matches = re.findall(pattern, input)
    return list(set(matches))  # get rid of duplicities


def parse_legacy_tags(meta: dict) -> list[str]:
    """Parses the space/comma-separated tags string from Legacy metadata into a list."""
    tags_str = meta.get("tags", "")
    return [
        tag.strip()
        for part in tags_str.split(",")
        for tag in part.split()
        if tag.strip()
    ]


def resolve_kpi_description(legacy_client: LegacyClient, obj: dict[str, Any]) -> str:
    """Resolve the effective description of a Legacy KPI widget."""
    # Summary is only populated when description is set to `custom`. No visibility setting exists on custom summary.
    summary = obj["kpi"]["meta"]["summary"]
    if summary:
        return summary
    description_config = (
        obj["kpi"]["content"].get("configuration", {}).get("description", {})
    )
    # Description can be set to None in UI - `configuration.description.visible` = false
    if not description_config.get("visible", True):
        return ""

    # If description is not hidden and kpi.meta.summary is falsey, fall back to metric description
    metric_obj = legacy_client.get_object(obj["kpi"]["content"]["metric"])
    return metric_obj["metric"]["meta"].get("summary", "")


COMPUTED_ATTRIBUTE_PREFIXES = ("attr.comp.", "label.comp.")


def is_computed_attribute(legacy_identifier: str) -> bool:
    """Legacy computed attributes always use the attr.comp./label.comp. prefix."""
    return legacy_identifier.startswith(COMPUTED_ATTRIBUTE_PREFIXES)


def computed_attribute_cloud_id(legacy_identifier: str) -> str:
    """Cloud computed attribute id is the Legacy label id (label.comp.X)."""
    return "label." + legacy_identifier.split(".", 1)[1]


def cloud_display_form_type(legacy_identifier: str) -> str:
    """Entity type Cloud expects for a Legacy display form reference."""
    return "computedAttribute" if is_computed_attribute(legacy_identifier) else "label"


def get_cloud_id(title: str, legacy_identifier: str) -> str:
    """
    Returns the Cloud metric identifier.
    """
    cloud_metric_id = f"{text2identifier(title)}_{legacy_identifier}"
    return cloud_metric_id


def duration(start_time: float) -> int:
    """
    Returns the duration in seconds
    """
    return int((time() - start_time))


def slugify(text: str) -> str:
    """
    Convert text to lowercase ASCII, replacing spaces with underscores.
    """
    value = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return value.lower().replace(" ", "_")


def validate_non_null_string(value: Any, name: str) -> str:
    if not value:
        raise ValueError(f"{name} with value {value} not found in the mapping file")

    if not isinstance(value, str):
        raise ValueError(
            f"{name} with value {value} is not a string in the mapping file"
        )

    return value


@attrs.define
class ThreadSafeCount:
    """Counter using a thread-safe lock."""

    _count: int = attrs.field(default=0)
    _lock: threading.Lock = attrs.field(factory=threading.Lock)

    def increment(self) -> None:
        """Increase the counter by 1."""
        with self._lock:
            self._count = self._count + 1

    def get(self) -> int:
        """Return the current value of the counter."""
        with self._lock:
            return self._count

    def __str__(self) -> str:
        return f"{self.get()}"
