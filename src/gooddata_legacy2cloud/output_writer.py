# (C) 2026 GoodData Corporation
"""
This module contains the OutputWriter class,
which is used to write output to a file.
"""

import datetime
import json
import logging

from gooddata_legacy2cloud.backends.cloud.object_creator_strategy import (
    CLOUD_SKIPPED_COMPUTED_ATTRIBUTES_FILE,
    CLOUD_SKIPPED_DASHBOARDS_FILE,
    CLOUD_SKIPPED_INSIGHTS_FILE,
    CLOUD_SKIPPED_METRICS_FILE,
    CLOUD_SKIPPED_REPORTS_FILE,
)
from gooddata_legacy2cloud.helpers import ensure_directory_exists, prefix_filename
from gooddata_legacy2cloud.id_mappings import IdMappings

logger = logging.getLogger("migration")


class OutputWriter:
    """A class used to write output to a file."""

    def __init__(self, filename):
        """Constructs an OutputWriter with the given filename."""
        self.filename = prefix_filename(filename)
        self.mappings = IdMappings()

        # Ensure parent directory exists
        ensure_directory_exists(self.filename)

        # Create an empty file
        with open(self.filename, "w"):
            pass

    def _serialize_object(self, obj):
        """
        Helper method to properly serialize an object as JSON if possible.
        Falls back to string representation if JSON serialization fails.

        Args:
            obj: Object to serialize

        Returns:
            Serialized string representation of the object
        """
        if isinstance(obj, (dict, list)):
            try:
                # Use json.dumps with ensure_ascii=False to maintain unicode characters
                return json.dumps(obj, ensure_ascii=False)
            except TypeError, ValueError:
                # Fallback to string representation if JSON serialization fails
                return str(obj)
        else:
            # If it's not a dict or list, return it as is
            return str(obj)

    def write_dataset(self, dataset):
        """Writes a dataset to the file."""
        ensure_directory_exists(self.filename)
        with open(self.filename, "w+", encoding="utf-8") as file:
            file.write(f"{dataset}\n")

    def write_identifier_relation(self, legacy_identifier, cloud_identifier):
        """
        Writes a relation between
        Legacy identifier and Cloud identifier to the file.
        """
        self.mappings.add_mapping_identifier(legacy_identifier, cloud_identifier)

        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(f"{legacy_identifier},{cloud_identifier}\n")

    def write_transformation(self, title, legacy_object, cloud_object):
        """
        Generic method to write a transformation between Legacy and Cloud objects.

        Args:
            title: Title/header for the transformation
            legacy_object: The Legacy object to serialize and write
            cloud_object: The Cloud object to serialize and write
        """
        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(f"{title}\n")
            file.write(f"{self._serialize_object(legacy_object)}\n")
            file.write(f"{self._serialize_object(cloud_object)}\n\n")

    def append_content(self, content):
        """
        Appends arbitrary content to the file.

        Args:
            content: String content to append to the file
        """
        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(content)

    def write_migration_metadata(
        self,
        legacy_hostname,
        legacy_ws,
        cloud_hostname,
        cloud_ws,
        client_prefix=None,
    ):
        """
        Writes migration metadata as the first three lines of the log file.
        This is used by the web compare tool to identify migration details.

        Args:
            legacy_hostname: Legacy hostname/domain
            legacy_ws: Legacy workspace ID
            cloud_hostname: Cloud hostname/domain
            cloud_ws: Cloud workspace ID
            client_prefix: Optional client prefix used for this migration
        """
        timestamp = datetime.datetime.now().isoformat()

        line1 = f"timestamp={timestamp}"
        if client_prefix:
            line1 += f";client_prefix={client_prefix}"
        line2 = f"legacy-hostname={legacy_hostname};legacy-ws={legacy_ws}"

        line3 = f"cloud-hostname={cloud_hostname};cloud-ws={cloud_ws}"

        # Write with a special prefix to identify these lines
        with open(self.filename, "w", encoding="utf-8") as file:
            file.write(f"#MIGRATION_INFO#{line1}\n")
            file.write(f"#MIGRATION_INFO#{line2}\n")
            file.write(f"#MIGRATION_INFO#{line3}\n")
            file.write("\n")  # Empty line as divider

    def get_mappings(self):
        """Returns the mappings."""
        return self.mappings.get()

    def get_value_by_key(self, key):
        """Returns the value by key."""
        return self.mappings.get_value_by_key(key)

    def get_keys_by_value(self, cloud_identifier):
        """Returns key if the cloud identifier is in the mappings."""
        return self.mappings.get_keys_by_value(cloud_identifier)

    def write_skipped_objects(self, skipped_objects, object_type):
        """
        Writes the list of skipped Cloud object IDs to a JSON file.

        Args:
            skipped_objects (list): A list of skipped Cloud objects
            object_type (str): The type of objects ('metric', 'insight', 'dashboard', or 'report')

        Returns:
            str: The path to the written file
        """
        # Determine the appropriate filename based on object type
        if object_type == "metric":
            filename = CLOUD_SKIPPED_METRICS_FILE
        elif object_type == "insight":
            filename = CLOUD_SKIPPED_INSIGHTS_FILE
        elif object_type == "dashboard":
            filename = CLOUD_SKIPPED_DASHBOARDS_FILE
        elif object_type == "report":
            filename = CLOUD_SKIPPED_REPORTS_FILE
        elif object_type == "computed_attribute":
            filename = CLOUD_SKIPPED_COMPUTED_ATTRIBUTES_FILE
        else:
            raise ValueError(f"Unsupported object type: {object_type}")

        filepath = prefix_filename(filename)
        ensure_directory_exists(filepath)

        # Extract Cloud IDs from skipped objects
        skipped_ids = []
        for obj in skipped_objects:
            if "data" in obj and "id" in obj["data"]:
                skipped_ids.append(obj["data"]["id"])

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(skipped_ids, f, indent=2)

        logger.info(
            "Skipped %d %ss, IDs written to '%s'",
            len(skipped_ids),
            object_type,
            filepath,
        )
        return filepath
