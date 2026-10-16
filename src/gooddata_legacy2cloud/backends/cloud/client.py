# (C) 2026 GoodData Corporation

import concurrent.futures
import json
import logging
import time
from enum import Enum
from typing import Any, Type
from urllib.parse import quote

import requests
from gooddata_sdk import GoodDataSdk
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gooddata_legacy2cloud.constants import CLOUD_REQUEST_PAGE_SIZE
from gooddata_legacy2cloud.helpers import (
    DASHBOARD_SPECIFIC_INSIGHT_PREFIX,
    PP_DASHBOARD_PREFIX,
    PP_FILTER_CONTEXT_PREFIX,
    PP_INSIGHT_PREFIX,
    REPORT_INSIGHT_PREFIX,
    ThreadSafeCount,
)
from gooddata_legacy2cloud.models.cloud.attribute import AttributeWrapper
from gooddata_legacy2cloud.models.cloud.filter_context import FilterContextModel

logger = logging.getLogger("migration")

TIMEOUT = 60


class HttpMethod(Enum):
    # NOTE: Use StrEnum with python 3.11
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class RateLimitError(Exception):
    """Rate Limit exceeded without expected headers."""


DO_NOT_RETRY_EXCEPTIONS: tuple[Type[Exception], ...] = (
    RateLimitError,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
    requests.exceptions.InvalidURL,
    requests.exceptions.InvalidSchema,
)


class CloudClient:
    """A class used to interact with a server."""

    def __init__(
        self,
        domain: str,
        ws: str,
        token: str,
    ):
        """Constructs CloudClient object with given domain, workspace, and token."""
        self.domain = domain
        self.ws = ws
        self.token = token
        self.sdk = GoodDataSdk.create(
            host_=domain,
            token_=token,
        )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/vnd.gooddata.api+json",
        }

        self.request_count = ThreadSafeCount()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_not_exception_type(DO_NOT_RETRY_EXCEPTIONS),
    )
    def _request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """Sends a request to GoodData API with retry.

        If the response status code is 429, the function will wait for time
        indicated by X-RateLimit-Retry-After header and retry the request. If the
        X-RateLimit-Retry-After header is not present, an RateLimitError will be raised.

        Documentation related to the returned 429: https://www.gooddata.com/docs/cloud/api-and-sdk/api/errors/#http-status-code-429--too-many-requests

        The function will retry the request if an exception is raised, unless it
        is one of the exceptions listed in the DO_NOT_RETRY_EXCEPTIONS constant.

        Args:
            method: The HTTP method to use.
            endpoint: Endpoint to send the request to.
            data: JSON string of the request body.
            headers: The headers to send with the request. Will use self.headers if not provided.

        """
        request_method = method.value
        request_url = f"{self.domain}/{endpoint}"
        request_data = json.dumps(data) if data else None
        request_headers = headers or self.headers

        self.request_count.increment()

        response = requests.request(
            method=request_method,
            url=request_url,
            data=request_data,
            headers=request_headers,
            timeout=TIMEOUT,
        )

        if response.status_code == 429:
            retry_after = response.headers.get("X-RateLimit-Retry-After")
            if retry_after:
                # Sleep for the time indicated by the retry-after header
                time.sleep(int(retry_after))
                return self._request(method, endpoint, data, headers)
            else:
                # This case should not happen according to the docs -> let's fail loudly if it does
                raise RateLimitError(
                    "Rate limit exceeded, but no retry-after header:\n"
                    + f"URL: {request_url}\n"
                    + f"Method: {request_method}\n"
                    + f"Response Headers: {response.headers}\n"
                    + f"Response: {response.text}\n"
                )

        return response

    def _get(self, endpoint: str) -> Any:
        """Sends a GET request to the server and returns JSON object."""
        response = self._request(HttpMethod.GET, endpoint, headers=self.headers)
        response.raise_for_status()  # Raises HTTPError for bad status codes
        return response.json()

    def _post(
        self, endpoint: str, data: Any, headers: dict[str, str] | None = None
    ) -> requests.Response:
        """Sends a POST request to the server with a given JSON object."""
        return self._request(HttpMethod.POST, endpoint, data=data, headers=headers)

    def _put(
        self, endpoint: str, data: Any, headers: dict[str, str] | None = None
    ) -> requests.Response:
        """Sends a PUT request to the server with a given JSON object."""
        return self._request(HttpMethod.PUT, endpoint, data=data, headers=headers)

    def _delete(self, endpoint: str) -> requests.Response:
        """Sends a DELETE request to the server."""
        return self._request(HttpMethod.DELETE, endpoint, headers=self.headers)

    def check_parent_workspace(self):
        """
        Checks if the current workspace has a parent workspace.
        Returns:
            str or None: The ID of the parent workspace if it exists, None otherwise
        """
        url = f"api/v1/entities/workspaces/{self.ws}?include=parent"
        try:
            response = self._get(url)
            if (
                "relationships" in response["data"]
                and "parent" in response["data"]["relationships"]
            ):
                parent_data = response["data"]["relationships"]["parent"]["data"]
                if parent_data:
                    return parent_data.get("id")
            return None
        except (KeyError, Exception) as e:
            logger.error("Error checking parent workspace: %s", str(e))
            return None

    def put_model(self, p_ldm_json):
        """Sends a PUT request to the server with a given JSON object."""
        url = f"api/v1/layout/workspaces/{self.ws}/logicalModel"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        return self._put(url, p_ldm_json, headers)

    def get_model(self):
        """Sends a GET request to the server and returns JSON object."""
        url = f"api/v1/layout/workspaces/{self.ws}/logicalModel"
        return self._get(url)

    def get_ws_data_filters(self):
        """Sends a GET request to the server and returns JSON object."""
        url = f"api/v1/entities/workspaces/{self.ws}/workspaceDataFilters"
        try:
            return self._get(url)
        except requests.exceptions.RequestException as _e:
            return {"data": []}

    def remove_ws_data_filter(self, filter_id):
        """Sends a DELETE request to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/workspaceDataFilters/{filter_id}"
        return self._delete(url)

    def remove_all_ws_data_filters(self):
        """Removes all workspace data filters."""
        filters = self.get_ws_data_filters()

        for ws_filter in filters["data"]:
            self.remove_ws_data_filter(ws_filter["id"])

    def create_workspace_data_filters(self, ws_data_filters):
        """Sends a POST request to the server with a given JSON object."""
        url = f"api/v1/entities/workspaces/{self.ws}/workspaceDataFilters"

        for ws_filter in ws_data_filters:
            response = self._post(url, ws_filter)

            if response.status_code != 201:
                logger.error(
                    "Error creating workspace data filter: %s - %s",
                    response.status_code,
                    response.text,
                )

    def get_metrics(self, page=0, origin: str = "ALL"):
        """Sends a GET request to the server to get all metrics."""
        url = f"api/v1/entities/workspaces/{self.ws}/metrics?origin={origin}&size={CLOUD_REQUEST_PAGE_SIZE}&page={page}"
        try:
            result = self._get(url)
            data = result["data"]
            # If there are more pages, get them
            if len(data) == CLOUD_REQUEST_PAGE_SIZE:
                data.extend(self.get_metrics(page + 1))

            return data
        except KeyError:
            return []

    def create_metric(self, metric):
        """Post a metric to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/metrics"
        return self._post(url, metric)

    def update_metric(self, metric_id, metric):
        """Update a metric on the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/metrics/{metric_id}"
        return self._put(url, metric)

    def get_computed_attributes(self, page=0, origin: str = "ALL"):
        """Sends a GET request to the server to get all computed attributes."""
        url = f"api/v1/entities/workspaces/{self.ws}/computedAttributes?origin={origin}&size={CLOUD_REQUEST_PAGE_SIZE}&page={page}"
        try:
            result = self._get(url)
            data = result["data"]
            if len(data) == CLOUD_REQUEST_PAGE_SIZE:
                data.extend(self.get_computed_attributes(page + 1))
            return data
        except KeyError:
            return []

    def create_computed_attribute(self, computed_attribute):
        """Post a computed attribute to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/computedAttributes"
        return self._post(url, computed_attribute)

    def update_computed_attribute(self, computed_attribute_id, computed_attribute):
        """Update a computed attribute on the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/computedAttributes/{computed_attribute_id}"
        return self._put(url, computed_attribute)

    def remove_metric(self, metric_id):
        """Sends a DELETE request to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/metrics/{metric_id}"
        return self._delete(url)

    def remove_metrics(self, metrics):
        """Removes metrics from the server."""

        def remove_metric_wrapper(index, metric):
            logger.info("Removing %d: %s", index + 1, metric["id"])
            self.remove_metric(metric["id"])

        # Use ThreadPoolExecutor to remove metrics in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(remove_metric_wrapper, index, metric)
                for index, metric in enumerate(metrics)
            ]
            concurrent.futures.wait(futures)

    def get_insights(self, page=0, origin: str = "ALL"):
        """Sends a GET request to the server to get all insights."""
        url = f"api/v1/entities/workspaces/{self.ws}/visualizationObjects?origin={origin}&size={CLOUD_REQUEST_PAGE_SIZE}&page={page}"
        try:
            result = self._get(url)
            data = result["data"]
            # If there are more pages, get them
            if len(data) == CLOUD_REQUEST_PAGE_SIZE:
                data.extend(self.get_insights(page + 1))

            return data
        except KeyError:
            return []

    def create_insight(self, insight):
        """Post an insight to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/visualizationObjects"
        return self._post(url, insight)

    def update_insight(self, insight_id, insight):
        """Update an insight on the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/visualizationObjects/{insight_id}"
        return self._put(url, insight)

    def remove_insight(self, insight_id):
        """Sends a DELETE request to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/visualizationObjects/{insight_id}"
        return self._delete(url)

    def remove_insights(self, insights):
        """Removes insights from the server."""
        for index, insight in enumerate(insights):
            logger.info("Removing %d: %s", index + 1, insight["id"])
            self.remove_insight(insight["id"])

    def get_native_dashboard_specific_insights(self) -> list:
        """Gets only native dashboard-specific insights (those with the specific prefix)."""
        all_insights = self.get_insights(origin="NATIVE")
        result = []
        for insight in all_insights:
            if insight["id"].startswith(DASHBOARD_SPECIFIC_INSIGHT_PREFIX):
                result.append(insight)
        return result

    def filter_generic_insights(self, all_insights):
        """Returns generic insights, excluding insights created by migration scripts."""
        result = []
        for insight in all_insights:
            if (
                not insight["id"].startswith(DASHBOARD_SPECIFIC_INSIGHT_PREFIX)
                and not insight["id"].startswith(REPORT_INSIGHT_PREFIX)
                and not insight["id"].startswith(PP_INSIGHT_PREFIX)
            ):
                result.append(insight)
        return result

    def get_native_report_insights(self) -> list:
        """Removes only insights migrated from reports (those with the report prefix)."""
        all_insights = self.get_insights(origin="NATIVE")
        result = []
        for insight in all_insights:
            if insight["id"].startswith(REPORT_INSIGHT_PREFIX):
                result.append(insight)
        return result

    def get_color_palettes(self):
        """Sends a GET request to the server and returns JSON object."""
        url = f"{self.domain}/api/v1/entities/colorPalettes"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )
        return response.json()

    def create_color_palette(self, color_palette):
        """Sends a POST request to the server with a given JSON object."""
        url = "api/v1/entities/colorPalettes"
        response = self._post(url, color_palette)
        if response.status_code != 201:
            logger.error(
                "Error creating color palette: %s - %s",
                response.status_code,
                response.text,
            )

    def remove_color_palette(self, palette_id):
        """Sends a DELETE request to the server."""
        url = f"api/v1/entities/colorPalettes/{palette_id}"
        response = self._delete(url)
        if response.status_code != 204:
            logger.error(
                "Error removing color palette: %s - %s",
                response.status_code,
                response.text,
            )

    def remove_color_palettes(self):
        """Removes all color palettes."""
        color_palettes = self.get_color_palettes()

        for color_palette in color_palettes["data"]:
            self.remove_color_palette(color_palette["id"])

    def get_organization_settings(self):
        """Sends a GET request to the server and returns JSON object."""
        url = "api/v1/entities/organizationSettings"
        return self._get(url)

    def put_organization_settings(self, organization_settings):
        """Sends a PUT request to the server with a given JSON object."""
        url = f"api/v1/entities/organizationSettings/{organization_settings['data']['id']}"
        response = self._put(url, organization_settings)
        if response.status_code != 200:
            logger.error(
                "Error putting organization settings: %s - %s",
                response.status_code,
                response.text,
            )

    def get_organization_settings_with_filter(self, filter_param):
        """Sends a GET request to the server with filter and returns JSON object."""
        url = f"api/v1/entities/organizationSettings?filter={filter_param}"
        return self._get(url)

    def create_organization_setting(self, organization_setting):
        """Sends a POST request to create a new organization setting."""
        url = "api/v1/entities/organizationSettings"
        response = self._post(url, organization_setting)
        if response.status_code != 201:
            logger.error(
                "Error creating organization setting: %s - %s",
                response.status_code,
                response.text,
            )
        return response

    def get_dashboards(self, page=0, origin: str = "ALL") -> list[dict]:
        """Sends a GET request to the server to get all dashboards."""
        url = f"api/v1/entities/workspaces/{self.ws}/analyticalDashboards?origin={origin}&size={CLOUD_REQUEST_PAGE_SIZE}&page={page}"
        try:
            result = self._get(url)
            data = result["data"]
            # If there are more pages, get them
            if len(data) == CLOUD_REQUEST_PAGE_SIZE:
                data.extend(self.get_dashboards(page + 1))

            return data
        except KeyError:
            return []

    def create_dashboard(self, dashboard):
        """Post a dashboard to the server."""
        url = f"api/v1/entities/workspaces/{self.ws}/analyticalDashboards"
        return self._post(url, dashboard)

    def update_dashboard(self, dashboard_id, dashboard):
        """Update an existing dashboard on the server."""
        url = (
            f"api/v1/entities/workspaces/{self.ws}/analyticalDashboards/{dashboard_id}"
        )
        return self._put(url, dashboard)

    def remove_dashboard(self, dashboard_id):
        """Sends a DELETE request to the server."""
        url = (
            f"api/v1/entities/workspaces/{self.ws}/analyticalDashboards/{dashboard_id}"
        )
        return self._delete(url)

    def remove_dashboards(self, dashboards):
        """Removes dashboards from the server."""
        for index, dashboard in enumerate(dashboards):
            logger.info("Removing %d: %s", index + 1, dashboard["id"])
            self.remove_dashboard(dashboard["id"])

    def create_dashboard_permissions_for_public_dashboards(self, dashboard_ids):
        """Sends a POST request to the server with a given JSON object."""
        logger.info(
            "----Creating new dashboard permissions for public dashboards (%d)----",
            len(dashboard_ids),
        )
        for dashboard_id in dashboard_ids:
            url = f"api/v1/actions/workspaces/{self.ws}/analyticalDashboards/{dashboard_id}/managePermissions"
            permission = [
                {"assigneeRule": {"type": "allWorkspaceUsers"}, "permissions": ["VIEW"]}
            ]
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            response = self._post(url, permission, headers)
            if response.status_code != 204:
                logger.error(
                    "Error creating dashboard permissions for public dashboards: "
                    "%s - %s",
                    response.status_code,
                    response.text,
                )

    def create_filter_context(self, filter_context):
        """Sends a POST request to the server with a given JSON object."""
        logger.info("----Creating new filter context for dashboard----")
        url = f"api/v1/entities/workspaces/{self.ws}/filterContexts"
        response = self._post(url, filter_context)
        if response.status_code != 201:
            logger.error(
                "Error creating filter context: %s - %s",
                response.status_code,
                response.text,
            )
        return response

    def get_filter_context(self, filter_context_id) -> Any:
        """Sends a GET request to the server with a given JSON object."""
        url = f"api/v1/entities/workspaces/{self.ws}/filterContexts/{filter_context_id}"
        return self._get(url)

    def update_filter_context(self, filter_context):
        """Sends a PUT request to the server with a given JSON object."""
        logger.info("----Updating filter context for dashboard----")
        url = f"api/v1/entities/workspaces/{self.ws}/filterContexts/{filter_context['data']['id']}"
        response = self._put(url, filter_context)
        if not response.ok:
            logger.error(
                "Error updating filter context: %s - %s",
                response.status_code,
                response.text,
            )

    def get_filter_contexts(self, page=0, origin: str = "ALL") -> list[dict]:
        """Sends a GET request to the server to get all filter contexts."""
        url = f"api/v1/entities/workspaces/{self.ws}/filterContexts?origin={origin}&size={CLOUD_REQUEST_PAGE_SIZE}&page={page}"
        try:
            result = self._get(url)
            data = result["data"]
            # If there are more pages, get them
            if len(data) == CLOUD_REQUEST_PAGE_SIZE:
                data.extend(self.get_filter_contexts(page + 1))

            return data
        except KeyError:
            return []

    def get_filter_context_objects(self) -> list[FilterContextModel]:
        """Sends a GET request to the server to get all filter contexts."""
        filter_contexts = self.get_filter_contexts()
        return [FilterContextModel(**context) for context in filter_contexts]

    def remove_filter_contexts(self, filter_contexts):
        """Removes filter contexts."""

        for index, filter_context in enumerate(filter_contexts):
            logger.info("Removing %d: %s", index + 1, filter_context["id"])
            self.remove_filter_context(filter_context["id"])

    def remove_filter_context(self, filter_context_id):
        """Sends a DELETE request to the server with a given JSON object."""
        url = f"api/v1/entities/workspaces/{self.ws}/filterContexts/{filter_context_id}"
        return self._delete(url)

    def post_automation(self, automation):
        """Sends a POST request to the server with a given JSON object."""
        url = f"api/v1/entities/workspaces/{self.ws}/automations"
        return self._post(url, automation)

    def put_automation(self, automation):
        """Sends a POST request to the server with a given JSON object."""
        url = f"api/v1/entities/workspaces/{self.ws}/automations/{automation['data']['id']}"
        return self._put(url, automation)

    def get_automations_layout(self) -> list[dict]:
        url = f"api/v1/layout/workspaces/{self.ws}/automations"
        return self._get(url)

    def put_automations_layout(
        self, automations_layout: list[dict]
    ) -> requests.Response:
        url = f"api/v1/layout/workspaces/{self.ws}/automations"
        return self._put(url, automations_layout)

    def get_attribute_json(self, attribute_id: str) -> dict:
        """Sends a GET request to the server to get an attribute."""
        url = f"api/v1/entities/workspaces/{self.ws}/attributes/{attribute_id}"
        return self._get(url)

    def get_attribute_object(self, attribute_id: str) -> AttributeWrapper:
        """Sends a GET request to the server to get an attribute."""
        raw_response = self.get_attribute_json(attribute_id)
        validated_attribute = AttributeWrapper(**raw_response)
        return validated_attribute

    def remove_native_metrics(self) -> None:
        """Removes native metrics from the workspace."""
        native_metrics = self.get_metrics(origin="NATIVE")

        if native_metrics:
            logger.info("----Removing old Cloud metrics (%d)----", len(native_metrics))
            self.remove_metrics(native_metrics)
        else:
            logger.info("----No native metrics to remove----")

    def remove_native_insights(self) -> None:
        """Removes native insights from the workspace."""
        native_insights = self.get_insights(origin="NATIVE")
        generic_native_insights = self.filter_generic_insights(native_insights)

        if generic_native_insights:
            logger.info(
                "----Removing old Cloud insights (%d)----",
                len(generic_native_insights),
            )
            self.remove_insights(generic_native_insights)
        else:
            logger.info("----No native insights to remove----")

    def remove_native_report_insights(self) -> None:
        """Removes native report insights from the workspace."""
        native_report_insights = self.get_native_report_insights()

        if native_report_insights:
            logger.info(
                "----Removing old Cloud report insights (%d)----",
                len(native_report_insights),
            )
            self.remove_insights(native_report_insights)
        else:
            logger.info("----No native report insights to remove----")

    def remove_native_dashboards(self) -> None:
        """Removes native dashboards from the workspace (excluding PP dashboards)."""
        native_dashboards = [
            d
            for d in self.get_dashboards(origin="NATIVE")
            if not d["id"].startswith(PP_DASHBOARD_PREFIX)
        ]

        if native_dashboards:
            logger.info(
                "----Removing old Cloud dashboards and filter contexts (%d)----",
                len(native_dashboards),
            )
            self.remove_dashboards(native_dashboards)
        else:
            logger.info("----No native dashboards to remove----")

    def remove_native_filter_contexts(self) -> None:
        """Removes native filter contexts from the workspace (excluding PP contexts)."""
        native_filter_contexts = [
            fc
            for fc in self.get_filter_contexts(origin="NATIVE")
            if not fc["id"].startswith(PP_FILTER_CONTEXT_PREFIX)
        ]

        if native_filter_contexts:
            logger.info(
                "----Removing old Cloud filter contexts (%d)----",
                len(native_filter_contexts),
            )
            self.remove_filter_contexts(native_filter_contexts)
        else:
            logger.info("----No native filter contexts to remove----")

    def remove_native_dashboard_specific_insights(self) -> None:
        """Removes native dashboard-specific insights from the workspace."""
        native_dashboard_specific_insights = (
            self.get_native_dashboard_specific_insights()
        )

        if native_dashboard_specific_insights:
            logger.info(
                "----Removing old Cloud dashboard-specific insights (%d)----",
                len(native_dashboard_specific_insights),
            )
            self.remove_insights(native_dashboard_specific_insights)
        else:
            logger.info("----No native dashboard-specific insights to remove----")

    def get_native_pp_dashboards(self) -> list:
        """Gets only native pixel perfect dashboards (those with the PP dashboard prefix)."""
        all_dashboards = self.get_dashboards(origin="NATIVE")
        result = []
        for dashboard in all_dashboards:
            if dashboard["id"].startswith(PP_DASHBOARD_PREFIX):
                result.append(dashboard)
        return result

    def get_native_pp_insights(self) -> list:
        """Gets only native pixel perfect insights (headline visualizations)."""
        all_insights = self.get_insights(origin="NATIVE")
        result = []
        for insight in all_insights:
            if insight["id"].startswith(PP_INSIGHT_PREFIX):
                result.append(insight)
        return result

    def get_native_pp_filter_contexts(self) -> list:
        """Gets only native pixel perfect filter contexts (prefix: ppctx)."""
        all_filter_contexts = self.get_filter_contexts(origin="NATIVE")
        return [
            fc
            for fc in all_filter_contexts
            if fc["id"].startswith(PP_FILTER_CONTEXT_PREFIX)
        ]

    def remove_native_pp_dashboards(self) -> None:
        """Removes native pixel perfect dashboards from the workspace."""
        native_pp_dashboards = self.get_native_pp_dashboards()

        if native_pp_dashboards:
            logger.info(
                "----Removing %d pixel perfect dashboards----",
                len(native_pp_dashboards),
            )
            self.remove_dashboards(native_pp_dashboards)
        else:
            logger.info("----No native pixel perfect dashboards to remove----")

    def remove_native_pp_insights(self) -> None:
        """Removes native pixel perfect insights (headline visualizations)."""
        native_pp_insights = self.get_native_pp_insights()

        if native_pp_insights:
            logger.info(
                "----Removing %d pixel perfect insights----", len(native_pp_insights)
            )
            self.remove_insights(native_pp_insights)
        else:
            logger.info("----No native pixel perfect insights to remove----")

    def remove_native_pp_filter_contexts(self) -> None:
        """Removes native pixel perfect filter contexts."""
        native_pp_filter_contexts = self.get_native_pp_filter_contexts()

        if native_pp_filter_contexts:
            logger.info(
                "----Removing %d pixel perfect filter contexts----",
                len(native_pp_filter_contexts),
            )
            self.remove_filter_contexts(native_pp_filter_contexts)
        else:
            logger.info("----No native pixel perfect filter contexts to remove----")

    def get_users_by_emails(self, emails: list[str]) -> list[dict]:
        """
        Retrieves Cloud users by their email addresses using organization-level API.
        This allows finding users who exist in the organization but may not be in the workspace.

        Args:
            emails: List of email addresses to look up

        Returns:
            list: A list of user dictionaries matching the email addresses

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        if not emails:
            return []

        # Build filter using RSQL syntax: email=in=(email1,email2,...)
        # Limit to 50 emails per request to stay within URL length limits
        # (typical email ~30 chars, URL limit ~2000 chars, leaves room for base URL)
        batch_size = 50
        all_users = []

        for i in range(0, len(emails), batch_size):
            batch_emails = emails[i : i + batch_size]
            # URL-encode each email to handle special characters like + and @
            # Wrap each email in single quotes for RSQL syntax
            encoded_emails = [f"'{quote(email, safe='')}'" for email in batch_emails]
            email_filter = f"email=in=({','.join(encoded_emails)})"
            url = f"api/v1/entities/users?filter={email_filter}&size=1000"

            result = self._get(url)
            users = result.get("data", [])
            all_users.extend(users)

        return all_users

    def get_usergroups_by_names(self, names: list[str]) -> list[dict]:
        """
        Retrieves Cloud user groups by their names using organization-level API.

        Args:
            names: List of user group names to look up

        Returns:
            list: A list of user group dictionaries matching the names

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        if not names:
            return []

        # Build filter using RSQL syntax: name=in=(name1,name2,...)
        # Limit to 50 names per request to stay within URL length limits
        batch_size = 50
        all_usergroups = []

        for i in range(0, len(names), batch_size):
            batch_names = names[i : i + batch_size]
            # URL-encode each name to handle special characters
            # Wrap each name in single quotes for RSQL syntax
            encoded_names = [f"'{quote(name, safe='')}'" for name in batch_names]
            name_filter = f"name=in=({','.join(encoded_names)})"
            url = f"api/v1/entities/userGroups?filter={name_filter}&size=1000"

            result = self._get(url)
            usergroups = result.get("data", [])
            all_usergroups.extend(usergroups)

        return all_usergroups

    def get_workspace_layout(self) -> dict:
        """
        Retrieves the complete workspace analytics model layout.

        Returns:
            dict: The complete layout JSON including all analytics objects
        """
        url = f"api/v1/layout/workspaces/{self.ws}/analyticsModel"
        return self._get(url)

    def update_workspace_layout(self, layout: dict) -> requests.Response:
        """
        Updates the complete workspace analytics model layout.

        Args:
            layout: The complete layout JSON to PUT

        Returns:
            requests.Response: The response from the PUT request
        """
        url = f"api/v1/layout/workspaces/{self.ws}/analyticsModel"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        return self._put(url, layout, headers)
