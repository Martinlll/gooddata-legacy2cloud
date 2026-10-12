# (C) 2026 GoodData Corporation
"""
This module contains the IdMappings class, which handles the mapping
from Legacy identifiers to Cloud identifiers.
"""

import csv
import logging
import os

from gooddata_legacy2cloud.helpers import (
    computed_attribute_cloud_id,
    is_computed_attribute,
)

logger = logging.getLogger("migration")


class IdMappings:
    """
    Class takes care about Legacy to Cloud ID mapping
    """

    def __init__(self, files=None):
        """
        Initializes a new instance of the IdMappings class.

        Args:
            files: A single file path or a list of file paths to load mappings from.
                  If a file doesn't exist, a warning is printed but no error is raised.
        """
        self.id_mapping = {}
        self.loaded_files = []

        if files is not None:
            if isinstance(files, str):
                # Single file path
                self._load_file(files)
            elif isinstance(files, list):
                # Multiple file paths
                for file in files:
                    self._load_file(file)

    def _load_file(self, filename):
        """
        Load mappings from a CSV file.
        Returns True if the file was loaded successfully, False otherwise.
        """
        if not os.path.exists(filename):
            return False

        try:
            with open(filename, "r") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:  # Ensure we have at least two columns
                        self.id_mapping[row[0]] = row[1].strip()

            self.loaded_files.append(filename)
            return True
        except Exception as e:
            logger.warning("Error loading mapping file '%s': %s", filename, e)
            return False

    def add_mapping_identifier(self, key, value):
        """
        Adds a new mapping from a Legacy identifier to a Cloud identifier.
        """
        self.id_mapping[key] = value
        return

    def search_mapping_identifier(self, legacy_identifier):
        """
        Searches for the Cloud identifier corresponding to a Legacy identifier.
        """
        if legacy_identifier in self.id_mapping:
            return self.id_mapping[legacy_identifier]

        if is_computed_attribute(legacy_identifier):
            return computed_attribute_cloud_id(legacy_identifier)

        raise ValueError(
            f"Search Cloud Id - Unknown Legacy identifier {legacy_identifier}"
        )

    def find_similar(self, search):
        """
        Searches for the Cloud identifier corresponding to a Legacy identifier
        as there can be a similar identifier missing in the mapping (e.g. factsOf)
        """
        # try to find the whole second part first
        legacy_dataset = search.split(".", 1)[1]
        prefixes = [
            f"{p}.{legacy_dataset}" for p in ("attr", "label", "fact", "dataset")
        ]

        for key, value in self.id_mapping.items():
            if any(key.startswith(prefix) for prefix in prefixes):
                return value

        legacy_dataset = search.split(".")[1]
        prefixes = [
            f"{p}.{legacy_dataset}" for p in ("attr", "label", "fact", "dataset")
        ]

        for key, value in self.id_mapping.items():
            if any(key.startswith(prefix) for prefix in prefixes):
                return value

        raise ValueError(
            f"Search Cloud Id - Unknown similar Legacy identifier {search}"
        )

    def get_first_found_for_prefix(self, prefix):
        """
        Returns the first element based on the prefix.
        """
        for key, value in self.id_mapping.items():
            if key.startswith(prefix):
                return value

        raise ValueError(f"Get first element based on prefix - Unknown prefix {prefix}")

    def add_mapping_array(self, array):
        """
        Adds a new mapping from a Legacy identifier to a Cloud identifier.
        """
        self.id_mapping.update(array)

    def get(self):
        """Returns the mappings."""
        return self.id_mapping

    def get_loaded_files(self):
        """Returns the list of successfully loaded files."""
        return self.loaded_files

    def get_keys_by_value(self, value):
        """Returns all keys that have the given value."""
        return [key for key, val in self.id_mapping.items() if val == value]

    def get_value_by_key(self, key):
        """Returns the value by key."""
        return self.id_mapping.get(key)
