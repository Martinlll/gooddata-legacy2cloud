# (C) 2026 GoodData Corporation
import logging

from gooddata_legacy2cloud.constants import TIME_MACROS
from gooddata_legacy2cloud.helpers import get_cloud_id, is_computed_attribute
from gooddata_legacy2cloud.metrics.attribute_element import AttributeElement
from gooddata_legacy2cloud.metrics.contants import DELETED_VALUE, MISSING_VALUE
from gooddata_legacy2cloud.metrics.data_classes import MetricContext
from gooddata_legacy2cloud.metrics.maql.constants import (
    DATE_NUMBERS_WITH_TWO_DIGITS,
    DATE_TYPES_MAPPINGS,
    RELATION_OPERATORS,
    SHIFT_OPERATIONS,
)
from gooddata_legacy2cloud.metrics.maql.helpers import (
    DEFAULT_GRANULARITY,
    get_content_granularity,
    get_linked_objects,
)

logger = logging.getLogger("migration")


class ContentTreeModifier:
    """
    The ContentTreeModifier class is adjusting Legacy's content tree to become compatible with Cloud
    while constructing MAQL expressions.
    """

    def __init__(self, ctx: MetricContext, legacy_content_tree):
        self.ctx = ctx
        self.errors = []
        self.legacy_content_tree = legacy_content_tree

        # TODO consider get rid off object map creation
        linked_objects = get_linked_objects(legacy_content_tree["content"])
        self.object_map = self._get_uri_to_object_map(linked_objects)
        self.cloud_content_tree = self._process_tree(self.legacy_content_tree)

    def _process_tree(self, json_obj):
        type = json_obj["type"]

        if type in [
            "fact object",
            "attribute object",
            "metric object",
            "attributeDisplayForm object",
        ]:
            detailed_obj = self.object_map[json_obj["value"]]
            id = self._get_identifier(detailed_obj)
            json_obj["value"] = id
            json_obj["extra"] = {"type": detailed_obj["type"]}
            return json_obj

        elif type in ["attributeElement object"]:
            attElm = AttributeElement(self.ctx, json_obj["value"])

            if attElm.isMissingValue() or attElm.get() == DELETED_VALUE:
                self.errors.append(f"Missing value for {json_obj['value']}")

            json_obj["value"] = (
                MISSING_VALUE if attElm.get() == DELETED_VALUE else attElm.get()
            )
            json_obj["extra"] = {"type": attElm.get_type()}

            return json_obj

        elif type in ["prompt object"]:
            prompt_obj = self.ctx.legacy_client.get_prompt_project_object(
                json_obj["value"]
            )

            # only scalar prompts are supported
            if prompt_obj["type"] not in ["scalar"]:
                self.errors.append(
                    f"Prompt '{prompt_obj['type']}' is not supported - {json_obj['value']}"
                )

            json_obj["value"] = prompt_obj["expression"]
            return json_obj

        else:
            if "content" in json_obj:
                for content_item in json_obj["content"]:
                    content_item = self._process_tree(content_item)

                # handle the case when the content is a group
                json_obj = self._process_content_group(json_obj)

            return json_obj

    def _get_value_based_on_time_keyword(self, value, keyword):
        """
        Recalculates value to THIS context based on the given keyword.
        """
        if keyword == "PREVIOUS":
            return value - 1
        elif keyword == "NEXT":
            return value + 1
        return value

    def _apply_time_granularity_on_subtree(self, subtree, granularity):
        if "value" in subtree and subtree["value"] in TIME_MACROS:
            keyword = subtree["value"]
            subtree["value"] = f"{keyword}({granularity})"
        elif "content" in subtree:
            # propagate granularity within subtree content
            for content_item in subtree["content"]:
                content_item = self._apply_time_granularity_on_subtree(
                    content_item, granularity
                )

            # handle addition and subtraction of time macros
            if (
                subtree["type"] in SHIFT_OPERATIONS
                and subtree["content"][0]["type"] == "time macro"
                and subtree["content"][1]["type"] == "number"
            ):
                keyword, granularity = (
                    subtree["content"][0]["value"].replace(")", "").split("(")
                )

                value = int(subtree["type"] + subtree["content"][1]["value"])
                final_value = self._get_value_based_on_time_keyword(value, keyword)

                subtree["value"] = f"THIS({granularity}, {final_value})"
                subtree["type"] = "time macro"
        return subtree

    def _process_content_group(self, group):
        # adjust the date format values
        if (
            len(group["content"]) == 2
            and "type" in group
            and group["type"] in RELATION_OPERATORS
            and group["content"][0]["type"] == "attribute object"
            and group["content"][1]["type"] == "number"
            and "extra" in group["content"][0]
        ):
            expression_type = group["content"][0]["extra"]["type"]

            if expression_type in DATE_NUMBERS_WITH_TWO_DIGITS:
                group["content"][1] = {
                    "type": "string",
                    "value": group["content"][1]["value"].zfill(2),
                }
            elif expression_type == "GDC.time.day_in_year":
                group["content"][1] = {
                    "type": "string",
                    "value": group["content"][1]["value"].zfill(3),
                }
        elif (
            len(group["content"]) == 2
            and "type" in group
            and group["type"] in RELATION_OPERATORS
            and (
                group["content"][0]["type"] == "time macro"
                or group["content"][1]["type"] == "time macro"
            )
        ):
            granularity = get_content_granularity(group["content"])

            if group["content"][0]["type"] == "time macro":
                value = group["content"][0]["value"]
                group["content"][0]["value"] = f"{value}({granularity})"
            else:
                value = group["content"][1]["value"]
                group["content"][1]["value"] = f"{value}({granularity})"

        # handle PREVIOUS/THIS/NEXT in case of standalone time macro
        # e.g. Select THIS(day)
        # alternatively SELECT MAX(THIS(day))
        elif (
            len(group["content"]) == 1
            and "type" in group
            and (group["type"] == "expression" or group["type"] == "function")
            and group["content"][0]["type"] == "time macro"
        ):
            original_type = group["content"][0]["value"]
            group["content"][0]["value"] = f"{original_type}({DEFAULT_GRANULARITY})"

        # handle PREVIOUS/THIS/NEXT granularity propagation
        elif (
            len(group["content"]) == 2
            and group["content"][0]["type"] == "attribute object"
            and "type" in group
            and group["type"] in RELATION_OPERATORS
            and "extra" in group["content"][0]
            and "GDC.time" in group["content"][0]["extra"]["type"]
        ):
            expression_type = group["content"][0]["extra"]["type"]

            if expression_type in DATE_TYPES_MAPPINGS.keys():
                granularity = DATE_TYPES_MAPPINGS[expression_type]
                new_content = self._apply_time_granularity_on_subtree(
                    group["content"][1], granularity
                )
                group["content"][1] = new_content

        elif (
            len(group["content"]) == 3
            and group["content"][0]["type"] == "attribute object"
            and "type" in group
            and group["type"] in "between"
            and "GDC.time" in group["content"][0]["extra"]["type"]
        ):
            expression_type = group["content"][0]["extra"]["type"]

            if expression_type in DATE_TYPES_MAPPINGS.keys():
                granularity = DATE_TYPES_MAPPINGS[expression_type]

                for index in [1, 2]:
                    new_content = self._apply_time_granularity_on_subtree(
                        group["content"][index], granularity
                    )
                    group["content"][index] = new_content

        # adjust the COUNT where attributes are the same
        elif (
            len(group["content"]) == 2
            and "type" in group
            and group["type"] == "function"
            and group["value"] == "COUNT"
            and group["content"][0]["value"] == group["content"][1]["value"]
        ):
            group["content"] = [group["content"][0]]
        return group

    def _get_identifier(self, legacy_type_obj):
        """
        Searches for the Cloud identifier corresponding to a known Legacy identifier.
        """
        legacy_identifier = legacy_type_obj["id"]
        legacy_type = legacy_type_obj["type"]

        # if there is no exact match for Legacy identifier
        # (as it was omitted during the mapping process)
        if legacy_type_obj["id"].endswith("factsof"):
            prefix_index = legacy_identifier.find(".", legacy_identifier.find(".") + 1)
            prefix = legacy_identifier[:prefix_index]

            first_found = self.ctx.ldm_mappings.find_similar(prefix)
            dataset = first_found.split(".")[0]
            return f"{{dataset/{dataset}}}"

        # in case there should be a similar identifier
        try:
            if legacy_type == "metric":
                cloud_id = legacy_identifier  # it has been converted during the mapping process
            elif "GDC.time" in legacy_type:
                cloud_id = self.ctx.ldm_mappings.search_mapping_identifier(
                    legacy_identifier
                )
                legacy_type = "label"
            else:
                # everything else should be found in the mapping
                cloud_id = self.ctx.ldm_mappings.search_mapping_identifier(
                    legacy_identifier
                )

                # check Cloud identifier type as it can be dataset
                # (identifier without any separator is considered as dataset)
                if len(cloud_id.split(".")) == 1:
                    legacy_type = "dataset"

            return f"{{{legacy_type}/{cloud_id}}}"
        except ValueError as exc:
            raise ValueError(
                f"Search Cloud Id - Unknown Legacy identifier {legacy_identifier}"
            ) from exc

    def _get_uri_to_object_map(self, dependent_objects: list):
        """
        Returns a map of the dependent objects.
        e.g. /gdc/md/o4s6psxu1lp2n1pmd3ysy6tvm82ozt6y/obj/249 => {label/order.order_id}
        """
        objects_map = {}
        for object_item in dependent_objects:
            if object_item["type"] in [
                "fact object",
                "attribute object",
                "metric object",
                "attributeDisplayForm object",
            ]:
                key = object_item["value"]
                obj = self.ctx.legacy_client.get_object(key)

                if "fact" in obj:
                    objects_map[key] = {
                        "id": obj["fact"]["meta"]["identifier"],
                        "type": "fact",
                        "parent": object_item["parent"],
                    }
                elif "attribute" in obj:
                    if (
                        "type" in obj["attribute"]["content"]
                        and "GDC.time" in obj["attribute"]["content"]["type"]
                    ):
                        objects_map[key] = {
                            "id": obj["attribute"]["meta"]["identifier"],
                            "type": obj["attribute"]["content"]["type"],
                            "parent": object_item["parent"],
                        }
                    else:
                        attribute_id = obj["attribute"]["meta"]["identifier"]
                        objects_map[key] = {
                            "id": attribute_id,
                            "type": "computed_attribute"
                            if is_computed_attribute(attribute_id)
                            else "label",
                            "parent": object_item["parent"],
                        }
                elif "metric" in obj:
                    metric_meta = obj["metric"]["meta"]
                    original_id = metric_meta["identifier"]
                    metric_id = (
                        get_cloud_id(metric_meta["title"], original_id)
                        if not self.ctx.keep_original_ids
                        else original_id
                    )

                    objects_map[key] = {
                        "id": metric_id,
                        "type": "metric",
                        "parent": object_item["parent"],
                    }
                elif "attributeDisplayForm" in obj:
                    form_id = obj["attributeDisplayForm"]["content"]["formOf"]
                    form_id_obj = self.ctx.legacy_client.get_object(form_id)

                    objects_map[key] = {
                        "id": form_id_obj["attribute"]["meta"]["identifier"],
                        "type": "label",
                        "parent": object_item["parent"],
                    }
                else:
                    logger.warning("unknown obj type %s", obj)
            elif object_item["type"] in [
                "attributeElement object",
                "metric",
                "time macro",
                "number",
                "expression",
                "by",
                "function",
                "direction",
                "count",
                "string",
                "without pf",
                "with pf",
                "like",
                "ilike",
                "prompt object",
                "running function",
                "preceding",
                "following",
                "current",
                "window",
            ]:
                continue
            else:
                logger.warning("Unknown %s", object_item)

        return objects_map

    def get(self):
        return self.cloud_content_tree

    def get_errors(self):
        return list(set(self.errors))
