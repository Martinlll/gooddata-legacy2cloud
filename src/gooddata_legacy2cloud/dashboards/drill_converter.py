# (C) 2026 GoodData Corporation
"""
This module contains the DrillConverter class,
which is responsible for transforming Legacy drills to Cloud format.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from gooddata_legacy2cloud.dashboards.data_classes import DashboardContext
from gooddata_legacy2cloud.helpers import cloud_display_form_type

logger = logging.getLogger("migration")


@dataclass
class CurrentDashboard:
    """Information about the dashboard currently being processed."""

    legacy_id: str
    cloud_id: str


class MissingDashboardTargetError(Exception):
    """Exception raised when a drill target dashboard cannot be found."""

    def __init__(
        self,
        target_dashboard_id: str,
        source_object_id: str | None = None,
        drill_type: str | None = None,
    ):
        self.target_dashboard_id = target_dashboard_id
        self.source_object_id = source_object_id
        self.drill_type = drill_type
        super().__init__(f"Drill target dashboard '{target_dashboard_id}' not found")


class DrillConverter:
    """
    The DrillConverter class is responsible for transforming Legacy drills to Cloud format.
    """

    def __init__(self, ctx: DashboardContext):
        self.ctx = ctx
        # Regular expression to find attribute_title function calls in custom URLs
        self.attr_title_pattern = re.compile(r"{attribute_title\(([^)]+)\)}")
        # Regular expressions for the new functions
        self.attr_filter_selection_pattern = re.compile(
            r"{attribute_filter_selection\(([^)]+)\)}"
        )
        self.dash_attr_filter_selection_pattern = re.compile(
            r"{dash_attribute_filter_selection\(([^)]+)\)}"
        )

    def _get_attribute_identifier(self, legacy_attribute_id: str) -> dict:
        """Convert a Legacy attribute ID to a Cloud attribute identifier object."""
        cloud_id = self.ctx.ldm_mappings.search_mapping_identifier(legacy_attribute_id)
        return {
            "identifier": {
                "id": cloud_id,
                "type": cloud_display_form_type(legacy_attribute_id),
            }
        }

    def _transform_custom_url(self, url: str) -> list:
        """
        Transform a Legacy custom URL with placeholders to Cloud format.

        This method performs several transformations:
        1. Replaces Legacy-specific placeholders with Cloud equivalents
        2. Processes function calls:
           - attribute_title: Converts to Cloud attribute identifier objects, splitting the string
           - attribute_filter_selection and dash_attribute_filter_selection: Replaces Legacy IDs with
             Cloud IDs but keeps the functions in the string (no splitting)
        3. Returns an array where:
           - For attribute_title, the string is split and includes identifier objects
           - For other functions, the string keeps its format with only IDs replaced

        The returned format is an array where:
        - String elements represent static text segments
        - Dictionary elements represent dynamic attribute references formatted as Cloud identifiers
        """
        # Replace Legacy placeholders with Cloud ones
        url = url.replace("{insight_id}", "{visualization_id}")
        url = url.replace("{widget_id}", "")  # Remove widget_id placeholder
        # dashboard_id and workspace_id remain the same

        # First handle attribute_filter_selection and dash_attribute_filter_selection
        # which should remain as strings with only the IDs replaced

        # Process attribute_filter_selection
        def replace_filter_id(match):
            legacy_attr_id = match.group(1)
            try:
                cloud_id = self.ctx.ldm_mappings.search_mapping_identifier(
                    legacy_attr_id
                )
                return f"{{attribute_filter_selection({cloud_id})}}"
            except Exception as e:
                logger.warning(
                    "Error converting attribute_filter_selection(%s): %s",
                    legacy_attr_id,
                    e,
                )
                return match.group(0)  # Return original string on error

        # Process dash_attribute_filter_selection
        def replace_dash_filter_id(match):
            legacy_attr_id = match.group(1)
            try:
                cloud_id = self.ctx.ldm_mappings.search_mapping_identifier(
                    legacy_attr_id
                )
                return f"{{dash_attribute_filter_selection({cloud_id})}}"
            except Exception as e:
                logger.warning(
                    "Error converting dash_attribute_filter_selection(%s): %s",
                    legacy_attr_id,
                    e,
                )
                return match.group(0)  # Return original string on error

        # Replace filter function IDs in-place within the string
        url = self.attr_filter_selection_pattern.sub(replace_filter_id, url)
        url = self.dash_attr_filter_selection_pattern.sub(replace_dash_filter_id, url)

        # Now process attribute_title which requires splitting the string
        result = []
        last_end = 0

        # Find all attribute_title function calls
        for match in self.attr_title_pattern.finditer(url):
            # Add text before the function call
            if match.start() > last_end:
                result.append(url[last_end : match.start()])

            # Extract Legacy attribute ID and convert to Cloud identifier
            legacy_attr_id = match.group(1)
            result.append(self._get_attribute_identifier(legacy_attr_id))

            last_end = match.end()

        # Add remaining text after the last function call
        if last_end < len(url):
            result.append(url[last_end:])

        # If no attribute_title calls found, return the entire URL as a single string
        if not result:
            return [url]

        return result

    def _get_drill_origin(self, from_item: dict) -> dict:
        """Convert Legacy drill origin to Cloud format."""
        if "drillFromAttribute" in from_item:
            return {
                "type": "drillFromAttribute",
                "attribute": {
                    "localIdentifier": from_item["drillFromAttribute"][
                        "localIdentifier"
                    ]
                },
            }
        elif "drillFromMeasure" in from_item:
            return {
                "type": "drillFromMeasure",
                "measure": {
                    "localIdentifier": from_item["drillFromMeasure"]["localIdentifier"]
                },
            }
        else:
            # Default case, should not happen with valid input
            return {"type": "unknown"}

    def convert_drill_to_dashboard(
        self,
        drill: dict,
        widget_title: str | None = None,
        current_dashboard: Optional[CurrentDashboard] = None,
    ) -> dict:
        """Convert a Legacy drillToDashboard to Cloud format."""
        drill_to_dashboard = drill["drillToDashboard"]

        # Base drill structure
        cloud_drill = {
            "localIdentifier": str(uuid.uuid4()).replace("-", "")[:24],
            "transition": drill_to_dashboard.get("target", "in-place"),
            "origin": self._get_drill_origin(drill_to_dashboard["from"]),
            "type": "drillToDashboard",
        }

        # If there's no target dashboard specified, we're done.
        if "toDashboard" not in drill_to_dashboard:
            logger.info(
                "Drill is missing 'toDashboard' property. Creating drill without a target object."
            )
            return cloud_drill

        # --- If we get here, a target exists. Process it. ---
        legacy_dashboard_id = drill_to_dashboard["toDashboard"]
        drill_from = drill_to_dashboard["from"]
        drill_type = None
        local_identifier = None

        if "drillFromAttribute" in drill_from:
            drill_type = "drillFromAttribute"
            local_identifier = drill_from["drillFromAttribute"].get(
                "localIdentifier", "unknown"
            )
        elif "drillFromMeasure" in drill_from:
            drill_type = "drillFromMeasure"
            local_identifier = drill_from["drillFromMeasure"].get(
                "localIdentifier", "unknown"
            )

        # Create descriptive source object description
        if widget_title:
            if drill_type:
                source_object_id = (
                    f"'{widget_title}' ({drill_type}: {local_identifier})"
                )
            else:
                source_object_id = f"'{widget_title}' (unknown drill type)"
        else:
            source_object_id = (
                f"{drill_type}: {local_identifier}" if drill_type else "unknown"
            )

        # Try to find the Cloud dashboard ID
        try:
            # Check if it's a self-referencing drill
            if current_dashboard and legacy_dashboard_id == current_dashboard.legacy_id:
                cloud_dashboard_id = current_dashboard.cloud_id
            else:
                # Try to find in mappings using direct lookup
                cloud_dashboard_id = None
                if self.ctx.dashboard_mappings:
                    cloud_dashboard_id = self.ctx.dashboard_mappings.get_value_by_key(
                        legacy_dashboard_id
                    )

                # If not found in existing mappings, check current batch mappings
                if not cloud_dashboard_id and self.ctx.current_batch_dashboard_mappings:
                    cloud_dashboard_id = self.ctx.current_batch_dashboard_mappings.get(
                        legacy_dashboard_id
                    )

                if not cloud_dashboard_id:
                    raise MissingDashboardTargetError(
                        legacy_dashboard_id, source_object_id, drill_type
                    )
        except Exception:
            # Dashboard not found in mappings - raise error to skip this drill
            raise MissingDashboardTargetError(
                legacy_dashboard_id, source_object_id, drill_type
            )

        # Add the target to the drill object
        cloud_drill["target"] = {
            "identifier": {
                "id": cloud_dashboard_id,
                "type": "analyticalDashboard",
            }
        }

        return cloud_drill

    def convert_drill_to_visualization(self, drill: dict) -> dict:
        """Convert a Legacy drillToVisualization to Cloud format (becomes drillToInsight)."""
        visualization_uri = drill["drillToVisualization"]["toVisualization"]["uri"]

        # Get the visualization object to extract its identifier
        try:
            # Try to get the visualization object
            visualization_obj = self.ctx.legacy_client.get_object(visualization_uri)

            if "visualizationObject" not in visualization_obj:
                # This is not a valid visualization object
                logger.warning(
                    "Referenced URI is not a visualization object: %s",
                    visualization_uri,
                )
                raise ValueError(
                    f"Invalid visualization object structure: {visualization_uri}"
                )

            legacy_visualization_id = visualization_obj["visualizationObject"]["meta"][
                "identifier"
            ]

            # Try to find the Cloud insight ID
            try:
                cloud_insight_id = self.ctx.insight_mappings.search_mapping_identifier(
                    legacy_visualization_id
                )
            except ValueError as mapping_error:
                # Mapping not found, print warning and skip this drill
                logger.warning(
                    "Visualization mapping not found for '%s': %s. Skipping this drill.",
                    legacy_visualization_id,
                    mapping_error,
                )
                raise ValueError(
                    f"Cannot find insight mapping for: {legacy_visualization_id}"
                )

        except Exception as e:
            logger.warning("  Error processing visualization drill: %s", e)
            raise ValueError(f"Error processing visualization drill: {e}")

        return {
            "localIdentifier": str(uuid.uuid4()).replace("-", "")[:24],
            "transition": "pop-up",
            "origin": self._get_drill_origin(drill["drillToVisualization"]["from"]),
            "type": "drillToInsight",
            "target": {
                "identifier": {"id": cloud_insight_id, "type": "visualizationObject"}
            },
        }

    def convert_drill_to_custom_url(self, drill: dict) -> dict:
        """Convert a Legacy drillToCustomUrl to Cloud format."""
        url = drill["drillToCustomUrl"]["customUrl"]
        transformed_url = self._transform_custom_url(url)

        return {
            "localIdentifier": str(uuid.uuid4()).replace("-", "")[:24],
            "transition": "new-window",
            "origin": self._get_drill_origin(drill["drillToCustomUrl"]["from"]),
            "type": "drillToCustomUrl",
            "target": {"url": transformed_url},
        }

    def convert_drill_to_attribute_url(self, drill: dict) -> dict:
        """Convert a Legacy drillToAttributeUrl to Cloud format."""
        # Extract the URIs from the Legacy drill
        drill_to_attr_uri = drill["drillToAttributeUrl"]["drillToAttributeDisplayForm"][
            "uri"
        ]
        insight_attr_uri = drill["drillToAttributeUrl"]["insightAttributeDisplayForm"][
            "uri"
        ]

        # Get the attribute objects to extract their identifiers
        try:
            # Get the display form objects
            drill_to_attr_obj = self.ctx.legacy_client.get_object(drill_to_attr_uri)
            insight_attr_obj = self.ctx.legacy_client.get_object(insight_attr_uri)

            # Extract the Legacy identifiers
            # The structure should be something like {"attributeDisplayForm": {"meta": {"identifier": "..."}}}
            if (
                "attributeDisplayForm" not in drill_to_attr_obj
                or "attributeDisplayForm" not in insight_attr_obj
            ):
                logger.warning(
                    "Referenced URIs are not attribute display forms: %s, %s",
                    drill_to_attr_uri,
                    insight_attr_uri,
                )
                raise ValueError("Invalid attribute display form structure")

            legacy_hyperlink_id = drill_to_attr_obj["attributeDisplayForm"]["meta"][
                "identifier"
            ]
            legacy_display_id = insight_attr_obj["attributeDisplayForm"]["meta"][
                "identifier"
            ]

            # Convert Legacy identifiers to Cloud identifiers
            cloud_hyperlink_id = self.ctx.ldm_mappings.search_mapping_identifier(
                legacy_hyperlink_id
            )
            cloud_display_id = self.ctx.ldm_mappings.search_mapping_identifier(
                legacy_display_id
            )

        except Exception as e:
            logger.warning("  Error processing attribute URL drill: %s", e)
            raise ValueError(f"Error processing attribute URL drill: {e}")

        return {
            "localIdentifier": str(uuid.uuid4()).replace("-", "")[:24],
            "transition": "new-window",
            "origin": self._get_drill_origin(drill["drillToAttributeUrl"]["from"]),
            "type": "drillToAttributeUrl",
            "target": {
                "hyperlinkDisplayForm": {
                    "identifier": {"id": cloud_hyperlink_id, "type": "label"}
                },
                "displayForm": {
                    "identifier": {"id": cloud_display_id, "type": "label"}
                },
            },
        }

    def convert_drills(
        self,
        drills: list,
        widget_title: str | None = None,
        current_dashboard: Optional[CurrentDashboard] = None,
    ) -> tuple[list, list]:
        """
        Convert a list of Legacy drills to Cloud format.

        This method processes each drill individually, converting it to the appropriate Cloud format.
        It uses a resilient error handling approach where failures in individual drill conversions
        are caught and logged, but don't prevent the processing of other drills.

        This approach is used because:
        1. Missing some drills is preferable to failing the entire dashboard migration
        2. Each drill is independent, so errors in one shouldn't affect others
        3. We want to collect and report all issues rather than stopping at the first error

        Args:
            drills: List of Legacy drill objects to convert
            widget_title: Title of the widget containing these drills (for error messages)
            current_dashboard: Information about the dashboard currently being processed (for self-references)

        Returns a tuple of (successfully converted drills, drill warnings).
        """
        cloud_drills = []
        drill_warnings = []

        for i, drill in enumerate(drills):
            try:
                if "drillToDashboard" in drill:
                    cloud_drills.append(
                        self.convert_drill_to_dashboard(
                            drill, widget_title, current_dashboard
                        )
                    )
                elif "drillToVisualization" in drill:
                    cloud_drills.append(self.convert_drill_to_visualization(drill))
                elif "drillToCustomUrl" in drill:
                    cloud_drills.append(self.convert_drill_to_custom_url(drill))
                elif "drillToAttributeUrl" in drill:
                    cloud_drills.append(self.convert_drill_to_attribute_url(drill))
                else:
                    logger.warning("  Unknown drill type #%s: %s", i + 1, drill)
            except MissingDashboardTargetError as e:
                # Handle missing dashboard target specifically
                warning_msg = f"Drill to dashboard [{e.target_dashboard_id}] from object [{e.source_object_id}] could not be migrated. Target object does not exist."
                drill_warnings.append(warning_msg)
                logger.warning("  %s", warning_msg)
            except Exception as e:
                import traceback

                logger.error("Error converting drill #%s:", i + 1)
                logger.error("  Drill data: %s", drill)
                logger.error("  Error: %s", str(e))
                logger.error("  %s", traceback.format_exc())
                logger.error("  Skipping this drill, continuing with others.")
                # Continue with other drills without failing the entire dashboard

        return cloud_drills, drill_warnings
