# (C) 2026 GoodData Corporation
import logging
from abc import ABC, abstractmethod
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Type,
    TypedDict,
    TypeVar,
)

from requests import Response

from gooddata_legacy2cloud.backends.cloud.client import CloudClient
from gooddata_legacy2cloud.metrics.utils import disable_broken_metric
from gooddata_legacy2cloud.models.enums import Action

logger = logging.getLogger("migration")

CLOUD_FAILED_METRICS_FILE = "cloud_failed_metrics.json"
CLOUD_FAILED_INSIGHTS_FILE = "cloud_failed_insights.json"
CLOUD_FAILED_KPI_COMPARISON_INSIGHTS_FILE = "cloud_failed_kpi_comparison_insights.json"
CLOUD_FAILED_DASHBOARDS_FILE = "cloud_failed_dashboards.json"
CLOUD_FAILED_REPORTS_FILE = "cloud_failed_reports.json"
CLOUD_FAILED_PP_DASHBOARDS_FILE = "cloud_failed_pp_dashboards.json"
CLOUD_SKIPPED_METRICS_FILE = "cloud_skipped_metrics.json"
CLOUD_FAILED_COMPUTED_ATTRIBUTES_FILE = "cloud_failed_computed_attributes.json"
CLOUD_SKIPPED_COMPUTED_ATTRIBUTES_FILE = "cloud_skipped_computed_attributes.json"
CLOUD_SKIPPED_INSIGHTS_FILE = "cloud_skipped_insights.json"
CLOUD_SKIPPED_KPI_COMPARISON_INSIGHTS_FILE = (
    "cloud_skipped_kpi_comparison_insights.json"
)
CLOUD_SKIPPED_DASHBOARDS_FILE = "cloud_skipped_dashboards.json"
CLOUD_SKIPPED_REPORTS_FILE = "cloud_skipped_reports.json"
CLOUD_SKIPPED_PP_DASHBOARDS_FILE = "cloud_skipped_pp_dashboards.json"

# Define generic type for objects
T = TypeVar("T", bound=Dict[str, Any])


class CreationStrategy(ABC, Generic[T]):
    """Abstract base class for object creation strategies"""

    def __init__(self, cloud_client: CloudClient):
        self.cloud_client: CloudClient = cloud_client

    @abstractmethod
    def get_existing_objects(self) -> List[Dict]:
        """Retrieves existing objects from the server"""
        raise NotImplementedError("get_existing_objects not implemented")

    @abstractmethod
    def create_object(self, obj: T) -> Any:
        """Creates a single object on the server"""
        pass

    @abstractmethod
    def update_object(self, obj: T) -> Any:
        """Updates a single object on the server"""
        pass

    @abstractmethod
    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        pass

    @abstractmethod
    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        """Generates a link to the created object"""
        pass

    @abstractmethod
    def get_object_type(self) -> str:
        """Returns the type of object (metric, insight, dashboard)"""
        pass

    def get_success_status_codes(self) -> List[int]:
        """Returns the list of HTTP status codes that indicate success"""
        return [201]  # Default: 201 Created for POST operations

    def get_operation_name(self) -> str:
        """Returns the name of the operation being performed"""
        return "Creating"  # Default: Creating for POST operations

    def with_error_fallback(self, action: Action, obj: T) -> Any:
        """Creates or updates an object with error fallback"""

        create_or_update: Callable[[T], Any]

        if action == Action.CREATE:
            create_or_update = self.create_object
        elif action == Action.UPDATE:
            create_or_update = self.update_object

        response = create_or_update(obj)

        if response.ok:
            return response

        logger.error(
            "Cannot create - %s\n%s - %s\n",
            obj["data"]["attributes"]["title"],
            response.status_code,
            response.text,
        )

        fixed_metric = self.disable_object(obj, response)
        error_response = create_or_update(fixed_metric)

        if error_response.ok:
            logger.info(
                "%s error %s: %s\n",
                action.past().capitalize(),
                self.get_object_type(),
                fixed_metric["data"]["attributes"]["title"],
            )
        else:
            logger.error(
                "Cannot create error metric - %s\n%s - %s\n",
                fixed_metric["data"]["attributes"]["title"],
                error_response.status_code,
                error_response.text,
            )
        return error_response


class MetricCreationStrategy(CreationStrategy):
    """Strategy for creating metrics"""

    def get_existing_objects(self):
        return self.cloud_client.get_metrics()

    def create_object(self, obj: T) -> Any:
        return self.cloud_client.create_metric(obj)

    def update_object(self, obj: T) -> Any:
        return self.cloud_client.update_metric(obj["data"]["id"], obj)

    def disable_object(self, obj: T, response: Response) -> Any:
        return disable_broken_metric(obj, response)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/metrics/#/{workspace_id}/metric/{obj_id}/".replace("//", "/")

    def get_object_type(self) -> str:
        return "metric"


class ComputedAttributeCreationStrategy(CreationStrategy):
    """Strategy for creating computed attributes"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_computed_attributes()

    def create_object(self, obj: T) -> Any:
        return self.cloud_client.create_computed_attribute(obj)

    def update_object(self, obj: T) -> Any:
        return self.cloud_client.update_computed_attribute(obj["data"]["id"], obj)

    def disable_object(self, obj: T, response: Response) -> Any:
        return obj  # no placeholder for computed attributes

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/api/v1/entities/workspaces/{workspace_id}/computedAttributes/{obj_id}"

    def get_object_type(self) -> str:
        return "computed_attribute"


class InsightCreationStrategy(CreationStrategy):
    """Strategy for creating insights"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_insights()

    def create_object(self, obj: T) -> Any:
        return self.cloud_client.create_insight(obj)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/insights/#/{workspace_id}/insight/{obj_id}/".replace(
            "//", "/"
        )

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling insights"
        )

    def update_object(self, obj: T) -> Any:
        """Updates an insight"""
        return self.cloud_client.update_insight(obj["data"]["id"], obj)

    def get_object_type(self) -> str:
        return "insight"


# TODO: handle dashboard creation, dashboard update and dashboard placeholder in a single strategy object
class DashboardCreationStrategy(CreationStrategy):
    """Strategy for creating dashboards"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_dashboards()

    def create_object(self, obj: T) -> Any:
        return self.cloud_client.create_dashboard(obj)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/dashboards/#/{workspace_id}/dashboard/{obj_id}/".replace(
            "//", "/"
        )

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalid object content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling dashboards"
        )

    def update_object(self, obj: T) -> Any:
        """Updates a dashboard"""
        return self.cloud_client.update_dashboard(obj["data"]["id"], obj)

    def get_object_type(self) -> str:
        return "dashboard"


class PlaceholderDashboardCreationStrategy(CreationStrategy):
    """Strategy for creating minimal placeholder dashboards"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_dashboards()

    def create_object(self, obj: T) -> Any:
        # Extract dashboard ID and title from the full dashboard object
        dashboard_id = obj["data"]["id"]
        dashboard_title = obj["data"]["attributes"]["title"]

        # Create minimal placeholder dashboard
        # TODO: load the template from elsewhere (a json file?)
        placeholder = {
            "data": {
                "type": "analyticalDashboard",
                "id": dashboard_id,
                "attributes": {
                    "content": {
                        "layout": {
                            "type": "IDashboardLayout",
                            "sections": [
                                {
                                    "type": "IDashboardLayoutSection",
                                    "header": {},
                                    "items": [
                                        {
                                            "type": "IDashboardLayoutItem",
                                            "size": {
                                                "xl": {"gridHeight": 22, "gridWidth": 4}
                                            },
                                            "widget": {
                                                "type": "richText",
                                                "content": "This is temporary dashboard used during the workspace migration",
                                                "localIdentifier": "temp-placeholder-widget",
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                        "version": "2",
                    },
                    "title": f"TEMP - {dashboard_title}",
                },
            }
        }
        return self.cloud_client.create_dashboard(placeholder)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/dashboards/#/{workspace_id}/dashboard/{obj_id}/".replace(
            "//", "/"
        )

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling dashboards"
        )

    def update_object(self, obj: T) -> Any:
        """Updates a dashboard"""
        return self.cloud_client.update_dashboard(obj["data"]["id"], obj)

    def get_object_type(self) -> str:
        return "dashboard"


class DashboardUpdateStrategy(CreationStrategy):
    """Strategy for updating existing dashboards with full content"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_dashboards()

    def create_object(self, obj: T) -> Any:
        # For updates, we use the dashboard ID and full object
        dashboard_id = obj["data"]["id"]
        return self.cloud_client.update_dashboard(dashboard_id, obj)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/dashboards/#/{workspace_id}/dashboard/{obj_id}/".replace(
            "//", "/"
        )

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling dashboards"
        )

    def update_object(self, obj: T) -> Any:
        """Updates a dashboard"""
        return self.cloud_client.update_dashboard(obj["data"]["id"], obj)

    def get_object_type(self) -> str:
        return "dashboard"

    def get_success_status_codes(self) -> List[int]:
        """Returns the list of HTTP status codes that indicate success for updates"""
        return [200]  # PUT operations return 200 OK

    def get_operation_name(self) -> str:
        """Returns the name of the operation being performed"""
        return "Updating"  # PUT operations are updates


class ReportCreationStrategy(CreationStrategy):
    """Strategy for creating reports.
    Reports are migrated as insights (visualizationObject) to Cloud.
    """

    def get_existing_objects(self) -> list:
        # Reports are created as insights.
        return self.cloud_client.get_insights()

    def create_object(self, obj: dict) -> Any:
        return self.cloud_client.create_insight(obj)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/reports/#/{workspace_id}/report/{obj_id}/".replace("//", "/")

    def get_object_type(self) -> str:
        return "report"

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling reports"
        )

    def update_object(self, obj: T) -> Any:
        """Updates a report"""
        return self.cloud_client.update_insight(obj["data"]["id"], obj)


class PPDashboardPlaceholderCreationStrategy(CreationStrategy):
    """Strategy for creating minimal placeholder pixel perfect dashboards"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_dashboards()

    def create_object(self, obj: T) -> Any:
        # Extract dashboard ID and title from the full dashboard object
        dashboard_id = obj["data"]["id"]
        dashboard_title = obj["data"]["attributes"]["title"]

        # Create minimal placeholder dashboard
        placeholder = {
            "data": {
                "type": "analyticalDashboard",
                "id": dashboard_id,
                "attributes": {
                    "content": {
                        "layout": {
                            "type": "IDashboardLayout",
                            "sections": [
                                {
                                    "type": "IDashboardLayoutSection",
                                    "header": {},
                                    "items": [
                                        {
                                            "type": "IDashboardLayoutItem",
                                            "size": {
                                                "xl": {"gridHeight": 22, "gridWidth": 4}
                                            },
                                            "widget": {
                                                "type": "richText",
                                                "content": "This is temporary dashboard used during the workspace migration",
                                                "localIdentifier": "temp-placeholder-widget",
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                        "version": "2",
                    },
                    "title": f"TEMP - {dashboard_title}",
                },
            }
        }
        return self.cloud_client.create_dashboard(placeholder)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/dashboards/#/{workspace_id}/dashboard/{obj_id}/".replace(
            "//", "/"
        )

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling dashboards"
        )

    def update_object(self, obj: T) -> Any:
        """Updates a dashboard"""
        return self.cloud_client.update_dashboard(obj["data"]["id"], obj)

    def get_object_type(self) -> str:
        return "dashboard"


class PPDashboardUpdateStrategy(CreationStrategy):
    """Strategy for updating existing pixel perfect dashboards with full content"""

    def get_existing_objects(self) -> List[Dict]:
        return self.cloud_client.get_dashboards()

    def create_object(self, obj: T) -> Any:
        # For updates, we use the dashboard ID and full object
        dashboard_id = obj["data"]["id"]
        return self.cloud_client.update_dashboard(dashboard_id, obj)

    def get_object_link(self, domain: str, workspace_id: str, obj_id: str) -> str:
        return f"{domain}/dashboards/#/{workspace_id}/dashboard/{obj_id}/".replace(
            "//", "/"
        )

    def disable_object(self, obj: T, response: Response) -> Any:
        """Replaces an invalidobject content with a valid placeholder"""
        raise NotImplementedError(
            "disable_object method not implemented for disabling dashboards"
        )

    def update_object(self, obj: T) -> Any:
        """Updates a dashboard"""
        return self.cloud_client.update_dashboard(obj["data"]["id"], obj)

    def get_object_type(self) -> str:
        return "dashboard"

    def get_success_status_codes(self) -> List[int]:
        """Returns the list of HTTP status codes that indicate success for updates"""
        return [200]  # PUT operations return 200 OK

    def get_operation_name(self) -> str:
        """Returns the name of the operation being performed"""
        return "Updating"  # PUT operations are updates


class ObjectConfig(TypedDict):
    strategy_class: Type[CreationStrategy]
    failed_file: str
    skipped_file: str
    log_file_mode: str


# TODO: Clean up the object config and strategies so that there is truly one
# strategy per object type - dsahboard creation, update and placeholder creation
# could probably be merged into a single strategy

# Define object types and their corresponding files
OBJECT_CONFIG: Dict[str, ObjectConfig] = {
    "metric": {
        "strategy_class": MetricCreationStrategy,
        "failed_file": CLOUD_FAILED_METRICS_FILE,
        "skipped_file": CLOUD_SKIPPED_METRICS_FILE,
        "log_file_mode": "w",
    },
    "computed_attribute": {
        "strategy_class": ComputedAttributeCreationStrategy,
        "failed_file": CLOUD_FAILED_COMPUTED_ATTRIBUTES_FILE,
        "skipped_file": CLOUD_SKIPPED_COMPUTED_ATTRIBUTES_FILE,
        "log_file_mode": "w",
    },
    "insight": {
        "strategy_class": InsightCreationStrategy,
        "failed_file": CLOUD_FAILED_INSIGHTS_FILE,
        "skipped_file": CLOUD_SKIPPED_INSIGHTS_FILE,
        "log_file_mode": "w",
    },
    "kpi_comparison_insight": {
        "strategy_class": InsightCreationStrategy,
        "failed_file": CLOUD_FAILED_KPI_COMPARISON_INSIGHTS_FILE,
        "skipped_file": CLOUD_SKIPPED_KPI_COMPARISON_INSIGHTS_FILE,
        "log_file_mode": "a",
    },
    "dashboard": {
        "strategy_class": DashboardCreationStrategy,
        "failed_file": CLOUD_FAILED_DASHBOARDS_FILE,
        "skipped_file": CLOUD_SKIPPED_DASHBOARDS_FILE,
        "log_file_mode": "w",
    },
    "dashboard_update": {
        "strategy_class": DashboardUpdateStrategy,
        "failed_file": CLOUD_FAILED_DASHBOARDS_FILE,
        "skipped_file": CLOUD_SKIPPED_DASHBOARDS_FILE,
        "log_file_mode": "a",
    },
    "placeholder_dashboard": {
        "strategy_class": PlaceholderDashboardCreationStrategy,
        "failed_file": CLOUD_FAILED_DASHBOARDS_FILE,
        "skipped_file": CLOUD_SKIPPED_DASHBOARDS_FILE,
        "log_file_mode": "w",
    },
    "report": {
        "strategy_class": ReportCreationStrategy,
        "failed_file": CLOUD_FAILED_REPORTS_FILE,
        "skipped_file": CLOUD_SKIPPED_REPORTS_FILE,
        "log_file_mode": "w",
    },
    "pp_dashboard_placeholder": {
        "strategy_class": PPDashboardPlaceholderCreationStrategy,
        "failed_file": CLOUD_FAILED_PP_DASHBOARDS_FILE,
        "skipped_file": CLOUD_SKIPPED_PP_DASHBOARDS_FILE,
        "log_file_mode": "w",
    },
    "pp_dashboard_update": {
        "strategy_class": PPDashboardUpdateStrategy,
        "failed_file": CLOUD_FAILED_PP_DASHBOARDS_FILE,
        "skipped_file": CLOUD_SKIPPED_PP_DASHBOARDS_FILE,
        "log_file_mode": "a",
    },
}
