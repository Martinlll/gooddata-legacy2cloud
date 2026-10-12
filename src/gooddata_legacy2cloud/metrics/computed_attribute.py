# (C) 2026 GoodData Corporation
"""
Transforms Legacy computed attributes (attr.comp.X + label.comp.X) into Cloud
computed attribute entities defined by a MAQL CASE expression.
"""

import logging
import re

from gooddata_legacy2cloud.backends.legacy.client import LegacyClient
from gooddata_legacy2cloud.helpers import (
    computed_attribute_cloud_id,
    is_computed_attribute,
    parse_legacy_tags,
)
from gooddata_legacy2cloud.metrics.data_classes import MetricContext

logger = logging.getLogger("migration")

_WHEN = (
    r"when \{(?P<metric>[^}]+)\} (?P<op><=|<|>=|>|=) (?P<value>-?\d+(?:\.\d+)?) "
    r'then \{[^?}]+\?"(?P<label>[^"]*)"\}'
)
_ELSE = r'else \{[^?}]+\?"(?P<else_label>[^"]*)"\}'
# ponytail: strict grammar covering every CA seen so far (single metric,
# numeric thresholds, literal labels); extend when a real CA does not match
_REL = re.compile(
    rf"^to \{{(?P<base>[^}}]+)\}} as case (?P<whens>(?:{_WHEN}(?:, )?)+) ?(?:{_ELSE})? ?end$",
    re.S,
)
_WHEN_RE = re.compile(_WHEN)
_ELSE_RE = re.compile(_ELSE)


def fetch_legacy_computed_attributes(legacy_client: LegacyClient) -> list[dict]:
    """Returns full Legacy attribute objects of all computed attributes."""
    entries = legacy_client.get_attributes()["query"]["entries"]
    return [
        legacy_client.get_object(entry["link"])
        for entry in entries
        if is_computed_attribute(entry.get("identifier", ""))
    ]


def build_cloud_computed_attribute(ctx: MetricContext, attribute: dict) -> dict:
    """
    Builds a Cloud computed attribute entity from a Legacy attribute object.

    Args:
        ctx: Metric context with ldm and metric mappings.
        attribute: Legacy attribute object (``{"attribute": {...}}``).

    Returns:
        Cloud entity payload for POST /computedAttributes.

    Raises:
        ValueError: If the Legacy definition does not match the supported grammar
            or references unknown objects.
    """
    meta = attribute["attribute"]["meta"]
    relations = attribute["attribute"]["content"].get("rel", [])
    if len(relations) != 1:
        raise ValueError(f"Expected exactly one relation, got {len(relations)}")

    match = _REL.match(relations[0].strip())
    if not match:
        raise ValueError(f"Unsupported computed attribute definition: {relations[0]}")

    if ctx.metric_mappings is None:
        raise ValueError("Metric mappings are required for computed attributes")

    branches = []
    for when in _WHEN_RE.finditer(match["whens"]):
        metric_id = ctx.metric_mappings.search_mapping_identifier(when["metric"])
        branches.append(
            f"WHEN SUM({{metric/{metric_id}}}) {when['op']} {when['value']} "
            f'THEN "{when["label"]}"'
        )
    else_match = _ELSE_RE.search(relations[0])
    if else_match:
        branches.append(f'ELSE "{else_match["else_label"]}"')

    base_id = ctx.ldm_mappings.search_mapping_identifier(match["base"])
    maql = (
        "SELECT CASE " + " ".join(branches) + f" END BY {{label/{base_id}}} ALL OTHER"
    )

    return {
        "data": {
            "type": "computedAttribute",
            "id": computed_attribute_cloud_id(meta["identifier"]),
            "attributes": {
                "title": meta["title"],
                "description": meta.get("summary", ""),
                "tags": parse_legacy_tags(meta),
                "dataType": "STRING",
                "content": {"maql": maql},
            },
        }
    }


def build_cloud_computed_attributes(
    ctx: MetricContext, attributes: list[dict]
) -> list[dict]:
    """Builds all computed attributes, logging and skipping the invalid ones."""
    result = []
    for attribute in attributes:
        meta = attribute["attribute"]["meta"]
        try:
            result.append(build_cloud_computed_attribute(ctx, attribute))
        except ValueError as exc:
            logger.error(
                "Computed attribute '%s' (%s) cannot be migrated: %s",
                meta["title"],
                meta["identifier"],
                exc,
            )
    return result
