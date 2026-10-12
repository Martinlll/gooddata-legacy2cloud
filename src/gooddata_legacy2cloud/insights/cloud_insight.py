# (C) 2026 GoodData Corporation
"""
This module contains the CloudInsight class,
which is responsible for transforming the Legacy insight to Cloud format.
"""

import json
import logging
import uuid

from gooddata_legacy2cloud.helpers import (
    cloud_display_form_type,
    get_cloud_id,
    parse_legacy_tags,
)
from gooddata_legacy2cloud.id_mappings import IdMappings
from gooddata_legacy2cloud.insights.data_classes import InsightContext
from gooddata_legacy2cloud.insights.period_comparison_insight import (
    PeriodComparisonInsight,
)
from gooddata_legacy2cloud.metrics.attribute_element import AttributeElement
from gooddata_legacy2cloud.metrics.contants import DELETED_VALUE
from gooddata_legacy2cloud.metrics.cyclical_date_conversion import (
    _is_cyclical_legacy_attribute,
    convert_cyclical_date_elements,
)

logger = logging.getLogger("migration")


class CloudInsight:
    """
    The CloudInsight class is responsible for transforming the Legacy insight to Cloud format.
    """

    def __init__(
        self,
        ctx: InsightContext,
        metadata: dict,
    ):
        self.ctx = ctx
        self.meta = metadata["visualizationObject"]["meta"]
        self.insights_content = metadata["visualizationObject"]["content"]
        self.links = metadata["visualizationObject"]["links"]
        self.missing_filter_values: dict = {}
        self.missing_color_values: dict = {}
        self.attribute_filter_configs = {}
        self.filters = self._get_filters(
            self.insights_content.get("filters", []), "generic filters"
        )
        self.buckets = self._get_buckets(self.insights_content.get("buckets", []))
        self.sorts = self._get_sorts(self.insights_content.get("properties"))
        self.properties = self._get_properties(self.insights_content.get("properties"))
        self.visualization_url = self._get_visualization_url(
            self.insights_content["visualizationClass"]["uri"]
        )
        if self.ctx.keep_original_ids:
            self.cloud_insight_id = self.meta["identifier"]
        else:
            self.cloud_insight_id = get_cloud_id(
                self.meta["title"], self.meta["identifier"]
            )
        self.title, self.description = self._get_title_and_description()

    def _get_title_and_description(self):
        has_measure_value = any("measureValueFilter" in f for f in self.filters)
        has_ranking = any("rankingFilter" in f for f in self.filters)
        title = self.meta["title"]
        description = self.meta.get("summary", "")
        if self.missing_filter_values:
            if not self.ctx.suppress_warnings:
                title = f"[WARN] {self.meta['title']}"
                description += f"\nMigration errors - missing values in filters: {self.missing_filter_values}"
            logger.warning(
                "  Insight '%s': Missing values in filters: %s",
                self.meta["title"],
                self.missing_filter_values,
            )
        if self.missing_color_values:
            if not self.ctx.suppress_warnings:
                description += (
                    f"\nMissing values in color mapping: {self.missing_color_values}"
                )
            logger.info(
                "  Insight '%s': Missing values in color mapping: %s",
                self.meta["title"],
                self.missing_color_values,
            )
        if has_measure_value and has_ranking:
            if not self.ctx.suppress_warnings:
                title = f"[WARN] {self.meta['title']}"
                description += f"\nMeasure value and ranking filters not supported together. Please remove one category: {self.filters}"
            logger.warning(
                "  Insight '%s': Measure value and ranking filters not supported together. Please remove one category: %s",
                self.meta["title"],
                self.filters,
            )
        return title, description

    def _transform_identifier_in_boolean_filter(self, filter: dict, filter_name: str):
        obj = self.ctx.legacy_client.get_object(
            filter[filter_name]["displayForm"]["uri"]
        )
        new_local_identifier = uuid.uuid4().hex
        original_attribute_obj = self.ctx.legacy_client.get_object(
            obj["attributeDisplayForm"]["content"]["formOf"]
        )
        original_attribute_id = self.ctx.ldm_mappings.search_mapping_identifier(
            original_attribute_obj["attribute"]["meta"]["identifier"]
        )
        filter[filter_name]["displayForm"] = {
            "identifier": {
                "id": original_attribute_id,
                "type": self._transform_filter_type_value(obj),
            }
        }
        filter[filter_name]["localIdentifier"] = new_local_identifier

        new_attribute_filter_label_id = self.ctx.ldm_mappings.search_mapping_identifier(
            obj["attributeDisplayForm"]["meta"]["identifier"]
        )
        if new_attribute_filter_label_id != original_attribute_id:
            self.attribute_filter_configs[new_local_identifier] = {
                "displayAsLabel": {
                    "identifier": {
                        "id": new_attribute_filter_label_id,
                        "type": "label",
                    }
                }
            }
        return filter

    def _transform_identifier_in_date_filter(self, filter: dict, filter_name: str):
        obj = self.ctx.legacy_client.get_object(filter[filter_name]["dataSet"]["uri"])
        filter[filter_name]["dataSet"] = {
            "identifier": {
                "id": self.ctx.ldm_mappings.search_mapping_identifier(
                    obj["dataSet"]["content"]["identifierPrefix"]
                ),
                "type": obj["dataSet"]["meta"]["category"].lower(),
            }
        }
        return filter

    @staticmethod
    def _transform_filter_type_value(obj: dict) -> str:
        filter_type = obj["attributeDisplayForm"]["meta"]["category"].lower()
        if filter_type == "attributedisplayform":
            return cloud_display_form_type(
                obj["attributeDisplayForm"]["meta"]["identifier"]
            )
        return filter_type

    def _process_cyclical_date_filter(
        self, filter_type: str, filter: dict, origin: str
    ) -> tuple[dict | None, list]:
        """
        Process cyclical date filter using ID-based conversion.

        This method checks if the attribute filter is on a cyclical date attribute
        (day.in.week, quarter.in.year, etc.) and if so, uses ID-based conversion
        instead of AttributeElement to correctly convert the element values.

        Args:
            filter_type: "positiveAttributeFilter" or "negativeAttributeFilter"
            filter: The filter object
            origin: String describing filter origin for logging

        Returns:
            tuple: (new_filter, missing_values) or (None, []) if attribute not cyclical
        """
        try:
            # Get display form URI from filter
            display_form_uri = filter[filter_type]["displayForm"]["uri"]

            # Fetch the Legacy display form object to get its identifier
            display_form_obj = self.ctx.legacy_client.get_object(display_form_uri)

            # Extract Legacy identifier from the display form object
            if "attributeDisplayForm" not in display_form_obj:
                # Not a display form, return None to fallback
                return None, []

            legacy_identifier = display_form_obj["attributeDisplayForm"]["meta"][
                "identifier"
            ]

            # Check if this is a cyclical date attribute (using Legacy identifier)
            if not _is_cyclical_legacy_attribute(legacy_identifier):
                # Not a cyclical date, return None to fallback
                return None, []

            # Extract element URIs from filter
            filter_key = "notIn" if filter_type == "negativeAttributeFilter" else "in"
            element_uris = filter[filter_type][filter_key]

            # Convert using cyclical date conversion (using Legacy identifier)
            converted_values, missing_elements, null_elements = (
                convert_cyclical_date_elements(
                    self.ctx, element_uris, legacy_identifier
                )
            )

            # Build the transformed filter
            new_filter = self._transform_identifier_in_boolean_filter(
                filter, filter_type
            )

            # Combine converted values with nulls (represented as None in Cloud)
            all_values = converted_values + ([None] * len(null_elements))

            # Set the filter values
            new_filter[filter_type][filter_key] = {"values": all_values}

            # Track missing values if any
            missing_values = missing_elements if missing_elements else []

            return new_filter, missing_values

        except Exception as e:
            # Log the exception for debugging
            if not self.ctx.suppress_warnings:
                logger.debug("  Cyclical date filter detection failed: %s", e)
            # If anything goes wrong, return None to fallback to AttributeElement
            return None, []

    def _get_filters(self, filters: list, origin: str) -> list:
        new_filters = []
        for filter in filters:
            if "relativeDateFilter" in filter:
                new_filter = self._transform_identifier_in_date_filter(
                    filter, "relativeDateFilter"
                )
                new_filters.append(new_filter)

            elif "absoluteDateFilter" in filter:
                new_filter = self._transform_identifier_in_date_filter(
                    filter, "absoluteDateFilter"
                )
                new_filters.append(new_filter)

            elif "negativeAttributeFilter" in filter:
                # Try cyclical date conversion first
                cyclical_filter, cyclical_missing = self._process_cyclical_date_filter(
                    "negativeAttributeFilter", filter, origin
                )

                if cyclical_filter is not None:
                    # Successfully processed as cyclical date filter
                    if cyclical_missing:
                        key = f"{origin} - negativeAttributeFilter: {cyclical_filter['negativeAttributeFilter']['displayForm']['identifier']['id']}"
                        self.missing_filter_values[key] = cyclical_missing
                    new_filters.append(cyclical_filter)
                else:
                    # Not a cyclical date, use existing AttributeElement logic
                    missing_values = []
                    new_attribute_elements = []
                    new_filter = self._transform_identifier_in_boolean_filter(
                        filter, "negativeAttributeFilter"
                    )
                    resolved_elements = [
                        (
                            filter_in,
                            attr_element.get(),
                            attr_element.get_warning_uri(),
                        )
                        for filter_in in filter["negativeAttributeFilter"]["notIn"]
                        for attr_element in [AttributeElement(self.ctx, filter_in)]
                    ]
                    uris = [item[1] for item in resolved_elements]
                    if uris == [None]:  # Handle all except empty filter
                        new_filter["negativeAttributeFilter"]["notIn"] = {
                            "values": uris
                        }
                    elif (
                        "--MISSING VALUE--" in uris
                        or DELETED_VALUE in uris
                        or "" in uris
                    ):
                        for _original, new, warning_uri in resolved_elements:
                            if new in ["--MISSING VALUE--", ""]:
                                missing_values.append(warning_uri)
                            elif new == DELETED_VALUE:
                                continue
                            else:
                                new_attribute_elements.append(new)
                        new_filter["negativeAttributeFilter"]["notIn"] = {
                            "values": new_attribute_elements
                        }
                        if missing_values:
                            key = f"{origin} - negativeAttributeFilter: {new_filter['negativeAttributeFilter']['displayForm']['identifier']['id']}"
                            self.missing_filter_values[key] = missing_values
                    else:
                        new_filter["negativeAttributeFilter"]["notIn"] = {
                            "values": uris
                        }
                    new_filters.append(new_filter)

            elif "positiveAttributeFilter" in filter:
                # Try cyclical date conversion first
                cyclical_filter, cyclical_missing = self._process_cyclical_date_filter(
                    "positiveAttributeFilter", filter, origin
                )

                if cyclical_filter is not None:
                    # Successfully processed as cyclical date filter
                    if cyclical_missing:
                        key = f"{origin} - positiveAttributeFilter: {cyclical_filter['positiveAttributeFilter']['displayForm']['identifier']['id']}"
                        self.missing_filter_values[key] = cyclical_missing
                    new_filters.append(cyclical_filter)
                else:
                    # Not a cyclical date, use existing AttributeElement logic
                    missing_values = []
                    new_attribute_elements = []
                    new_filter = self._transform_identifier_in_boolean_filter(
                        filter, "positiveAttributeFilter"
                    )
                    resolved_elements = [
                        (
                            filter_in,
                            attr_element.get(),
                            attr_element.get_warning_uri(),
                        )
                        for filter_in in new_filter["positiveAttributeFilter"]["in"]
                        for attr_element in [AttributeElement(self.ctx, filter_in)]
                    ]
                    for original, new, warning_uri in resolved_elements:
                        if new == "--MISSING VALUE--":
                            missing_values.append(warning_uri)
                        elif new == DELETED_VALUE:
                            if origin == "measure filters" or warning_uri != original:
                                continue
                            missing_values.append(warning_uri)
                        else:
                            new_attribute_elements.append(new)

                    new_filter["positiveAttributeFilter"]["in"] = {
                        "values": new_attribute_elements
                    }
                    new_filters.append(new_filter)
                    if missing_values:
                        key = f"{origin} - positiveAttributeFilter: {new_filter['positiveAttributeFilter']['displayForm']['identifier']['id']}"
                        self.missing_filter_values[key] = missing_values

            elif "measureValueFilter" in filter:
                new_filters.append(filter)

            elif "rankingFilter" in filter:
                filter["rankingFilter"]["measure"] = filter["rankingFilter"][
                    "measures"
                ][0]
                del filter["rankingFilter"]["measures"]
                new_filters.append(filter)

        return new_filters

    def _transform_bucket(
        self, mapping: IdMappings, bucket: dict, legacy_object: dict, bucket_type: str
    ):
        cloud_id = mapping.search_mapping_identifier(
            legacy_object[bucket_type]["meta"]["identifier"]
        )
        bucket["measure"]["definition"]["measureDefinition"]["item"] = {
            "identifier": {
                "id": cloud_id,
                "type": legacy_object[bucket_type]["meta"]["category"],
            }
        }
        bucket["measure"]["definition"]["measureDefinition"]["filters"] = (
            self._get_filters(
                bucket["measure"]["definition"]["measureDefinition"].get("filters", []),
                "measure filters",
            )
        )
        return bucket

    def _get_new_measures(self, bucket: dict):
        new_items = []
        for item in bucket["items"]:
            if "arithmeticMeasure" in item["measure"]["definition"]:
                new_items.append(item)
            elif "measureDefinition" in item["measure"]["definition"]:
                legacy_link = item["measure"]["definition"]["measureDefinition"][
                    "item"
                ]["uri"]
                obj = self.ctx.legacy_client.get_object(legacy_link)

                if "metric" in obj:
                    item = self._transform_bucket(
                        self.ctx.metric_mappings, item, obj, "metric"
                    )
                    new_items.append(item)

                if "attribute" in obj or "fact" in obj:
                    (bucket_type,) = obj
                    item = self._transform_bucket(
                        self.ctx.ldm_mappings, item, obj, bucket_type
                    )
                    new_items.append(item)
            elif (
                "popMeasureDefinition" in item["measure"]["definition"]
                or "previousPeriodMeasure" in item["measure"]["definition"]
            ):
                item = PeriodComparisonInsight(self.ctx, item).get()
                new_items.append(item)
        return new_items

    def _get_new_attributes(self, bucket: dict):
        new_items = []
        for item in bucket["items"]:
            legacy_link = item["visualizationAttribute"]["displayForm"]["uri"]
            obj = self.ctx.legacy_client.get_object(legacy_link)
            item["displayForm"] = {
                "identifier": {
                    "id": self.ctx.ldm_mappings.search_mapping_identifier(
                        obj["attributeDisplayForm"]["meta"]["identifier"]
                    ),
                    "type": self._transform_filter_type_value(obj),
                }
            }
            item["localIdentifier"] = item["visualizationAttribute"]["localIdentifier"]

            if item["visualizationAttribute"].get("alias"):
                item["alias"] = item["visualizationAttribute"]["alias"]

            del item["visualizationAttribute"]
            new_items.append({"attribute": item})
        return new_items

    def _get_buckets(self, buckets: list[dict]):
        """
        Returns the buckets.
        """
        new_buckets = []
        for bucket in buckets:
            if bucket["localIdentifier"] in (
                "measures",
                "secondary_measures",
                "tertiary_measures",
            ):
                new_items = self._get_new_measures(bucket)
                new_buckets.append(
                    {"items": new_items, "localIdentifier": bucket["localIdentifier"]}
                )
            elif bucket["localIdentifier"] in (
                "attribute",
                "columns",
                "view",
                "trend",
                "segment",
                "stack",
                "attribute_from",
                "attribute_to",
            ):
                new_items = self._get_new_attributes(bucket)

                new_bucket = {
                    "items": new_items,
                    "localIdentifier": bucket["localIdentifier"],
                }

                if bucket.get("totals"):
                    new_bucket["totals"] = bucket["totals"]

                new_buckets.append(new_bucket)

            # TODO transform geo chart
        return new_buckets

    @staticmethod
    def _get_sorts(properties):
        if not properties:
            return []
        properties = json.loads(properties) if properties else {}
        sorts = properties.get("sortItems", [])
        return sorts

    def _get_properties(self, properties):
        if not properties:
            return {}
        references = self.insights_content.get("references", {})
        properties = json.loads(properties) if properties else {}
        properties.pop("sortItems", "")  # SortItems are resolved in the sorts

        controls = properties.get("controls", {})
        color_mapping = controls.get("colorMapping", {})
        new_color_mapping = []
        for color in color_mapping:
            if color["color"]["type"] == "guid":
                color["color"]["value"] = color["color"]["value"].replace("guid", "")
            if "id" in color and color["id"] in references:
                new_color = AttributeElement(self.ctx, references[color["id"]]).get()
                if new_color in ["--MISSING VALUE--", DELETED_VALUE, ""]:
                    key = f"colorMapping - {color['id']}"
                    self.missing_color_values[key] = references[color["id"]]
                else:
                    color["id"] = new_color
                    new_color_mapping.append(color)
        if new_color_mapping:
            properties["controls"]["colorMapping"] = new_color_mapping

        return properties

    def _get_visualization_url(self, visualization_class_uri: str):
        obj = self.ctx.legacy_client.get_object(visualization_class_uri)
        return obj["visualizationClass"]["content"]["url"]

    def get(self):
        """
        Returns the Cloud insight object.
        """

        if not self.buckets:
            logger.error(
                "  Insight '%s': not created as it does not contain any buckets.",
                self.meta["title"],
            )
            return

        self.ctx.mapping_logger.write_identifier_relation(
            self.meta["identifier"], self.cloud_insight_id
        )

        return {
            "data": {
                "id": self.cloud_insight_id,
                "type": "visualizationObject",
                "attributes": {
                    "title": self.title,
                    "description": self.description,
                    "tags": parse_legacy_tags(self.meta),
                    "createdAt": "",
                    "content": {
                        "filters": self.filters,
                        "attributeFilterConfigs": self.attribute_filter_configs,
                        "buckets": self.buckets,
                        "createdAt": self.meta["created"],
                        "modifiedAt": self.meta["updated"],
                        "sorts": self.sorts,
                        "properties": self.properties,
                        "visualizationUrl": self.visualization_url,
                        "version": "2",
                    },
                },
            }
        }
