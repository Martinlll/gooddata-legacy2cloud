# (C) 2026 GoodData Corporation

import logging

from gooddata_legacy2cloud.dashboard_permissions.data_classes import (
    DashboardPermissionContext,
)
from gooddata_legacy2cloud.id_mappings import IdMappings
from gooddata_legacy2cloud.layout.layout_manager import (
    update_object_creators_in_layout,
)
from gooddata_legacy2cloud.user_management.cloud_users import (
    build_cloud_email_user_map,
    extract_unique_emails_from_legacy_user_map,
)
from gooddata_legacy2cloud.user_management.data_classes import (
    ObjectUpdate,
    UserMapping,
)
from gooddata_legacy2cloud.user_management.legacy_users import (
    build_legacy_user_email_map,
    extract_creator_modifier_ids,
)
from gooddata_legacy2cloud.user_management.user_mapper import (
    map_legacy_to_cloud_users,
)

logger = logging.getLogger("migration")


class PermissionsUpdater:
    """
    Handles dashboard permissions updates from Legacy to Cloud.

    This class orchestrates the process of:
    - Fetching user information from Legacy and Cloud
    - Mapping users between systems
    - Processing dashboard permissions
    - Building updates for the Cloud layout
    """

    def __init__(self, context: DashboardPermissionContext):
        """
        Initialize the permissions updater.

        Args:
            context: Context containing APIs and configuration
        """
        self.ctx = context
        self.legacy_dashboards: list[dict] = []
        self.legacy_metrics: list[dict] = []
        self.legacy_insights: list[dict] = []
        self.legacy_user_map: dict[str, str] = {}
        self.cloud_user_map: dict[str, str] = {}
        self.user_mappings: dict[str, UserMapping] = {}
        self.all_grantee_emails: set[str] = set()
        self.all_grantee_group_names: set[str] = set()
        self.cloud_usergroup_map: dict[str, str] = {}

        # Determine identifier type based on context
        self.identifier_type = "email" if self.ctx.use_email else "login"
        self.identifier_plural = f"{self.identifier_type}s"

    def process_dashboards(
        self,
        legacy_dashboards: list[dict],
        legacy_metrics: list[dict] | None = None,
        legacy_insights: list[dict] | None = None,
    ) -> tuple[list[ObjectUpdate], dict[str, int]]:
        """
        Process Legacy dashboards (permissions + creators) and optionally
        metrics and insights (creators only) and prepare layout updates.

        Args:
            legacy_dashboards: List of Legacy dashboard objects
            legacy_metrics: List of Legacy metric objects
            legacy_insights: List of Legacy insight objects

        Returns:
            tuple: (list of ObjectUpdate instances, skip statistics dictionary)
        """
        self.legacy_dashboards = legacy_dashboards
        self.legacy_metrics = legacy_metrics or []
        self.legacy_insights = legacy_insights or []

        # Fetch and map users
        self._fetch_and_map_users()

        # Process each dashboard
        object_updates, skip_stats = self._build_object_updates()

        return object_updates, skip_stats

    def apply_layout_updates(
        self, layout: dict, object_updates: list[ObjectUpdate]
    ) -> tuple[dict, int, int, list]:
        """
        Apply permission updates to the Cloud workspace layout.

        Args:
            layout: The workspace layout dictionary
            object_updates: List of ObjectUpdate instances

        Returns:
            tuple: (modified_layout, updates_made, not_found_count, actual_changes)
        """

        return update_object_creators_in_layout(
            layout,
            object_updates,
            self.ctx.skip_creators,
            self.ctx.skip_individual_grantees,
            self.ctx.skip_group_grantees,
            self.ctx.permission_level,
            self.ctx.keep_existing_permissions,
        )

    def _fetch_and_map_users(self) -> None:
        """Fetch Legacy and Cloud users and create mappings."""
        # Collect grantee information if at least one type of grantee is not skipped
        if not self.ctx.skip_individual_grantees or not self.ctx.skip_group_grantees:
            logger.info("----Collecting grantee information from Legacy dashboards----")
            self._collect_grantee_emails()

        # Fetch Legacy users
        logger.info("----Fetching Legacy workspace users----")
        legacy_users = self.ctx.legacy_client.get_workspace_users()
        self.legacy_user_map = build_legacy_user_email_map(
            legacy_users, self.identifier_type
        )

        # Extract creator and modifier IDs
        user_ids = extract_creator_modifier_ids(
            self.legacy_dashboards + self.legacy_metrics + self.legacy_insights
        )
        logger.info(
            "Found %s unique creator/modifier %s in objects",
            len(user_ids),
            self.identifier_plural,
        )

        # Filter to only include relevant users
        filtered_legacy_user_map = self._filter_user_map_by_ids(user_ids)

        # Combine creator and grantee emails
        creator_emails = set(
            extract_unique_emails_from_legacy_user_map(filtered_legacy_user_map)
        )
        all_emails_to_lookup = creator_emails | self.all_grantee_emails

        # Fetch Cloud users
        logger.info("----Fetching relevant Cloud users by email----")
        cloud_users = self.ctx.cloud_client.get_users_by_emails(
            list(all_emails_to_lookup)
        )
        logger.info("Retrieved %s Cloud users from organization", len(cloud_users))
        self.cloud_user_map = build_cloud_email_user_map(cloud_users)

        # Map users
        logger.info("----Mapping users using %s field----", self.identifier_type)
        self.user_mappings = map_legacy_to_cloud_users(
            filtered_legacy_user_map,
            self.cloud_user_map,
            verbose=self.ctx.print_user_mappings,
        )

        self._print_mapping_statistics()

        # Fetch and map user groups (if not skipped)
        if not self.ctx.skip_group_grantees:
            self._fetch_and_map_usergroups()

    def _collect_grantee_emails(self) -> None:
        """Collect all grantee emails from Legacy dashboards."""
        logger.info("Fetching Dashboard permissions", extra={"end": "", "flush": True})
        for idx, obj in enumerate(self.legacy_dashboards, start=1):
            if not obj or len(obj) != 1:
                continue

            root_obj = next(iter(obj.values()))
            if not isinstance(root_obj, dict) or "meta" not in root_obj:
                continue

            # Extract numerical ID from URI
            dashboard_meta = root_obj["meta"]
            uri = dashboard_meta.get("uri", "")
            numerical_id = uri.split("/")[-1] if uri else None

            if numerical_id:
                grantees_data = self.ctx.legacy_client.get_object_grantees(numerical_id)
                emails, group_names = self._extract_grantees(grantees_data)
                if not self.ctx.skip_individual_grantees:
                    self.all_grantee_emails.update(emails)
                if not self.ctx.skip_group_grantees:
                    self.all_grantee_group_names.update(group_names)

        logger.info(" Done")
        if not self.ctx.skip_individual_grantees:
            logger.info(
                "Found %s unique grantee %s",
                len(self.all_grantee_emails),
                self.identifier_plural,
            )
        if not self.ctx.skip_group_grantees:
            logger.info(
                "Found %s unique grantee user groups",
                len(self.all_grantee_group_names),
            )

    def _extract_grantees(self, grantees_data: dict) -> tuple[list[str], list[str]]:
        """
        Extract emails/logins and user group names from grantees response.

        Args:
            grantees_data: Grantees API response

        Returns:
            tuple: (list of emails/logins, list of user group names)
        """
        emails = []
        group_names = []
        items = grantees_data.get("grantees", {}).get("items", [])

        for item in items:
            acl_entry = item.get("aclEntry", {})
            grantee = acl_entry.get("grantee", {})

            # Check if grantee is a user
            if "user" in grantee:
                user_content = grantee["user"].get("content", {})
                identifier = (
                    user_content.get("email")
                    if self.ctx.use_email
                    else user_content.get("login")
                )
                if identifier:
                    emails.append(identifier.lower())

            # Check if grantee is a user group
            elif "userGroup" in grantee:
                usergroup_content = grantee["userGroup"].get("content", {})
                group_name = usergroup_content.get("name")
                if group_name:
                    group_names.append(group_name)

        return emails, group_names

    def _filter_user_map_by_ids(self, user_ids: set[str]) -> dict[str, str]:
        """Filter user map to only include specified user IDs."""
        return {
            user_id: email
            for user_id, email in self.legacy_user_map.items()
            if user_id in user_ids
        }

    def _print_mapping_statistics(self) -> None:
        """Print statistics about user mappings."""
        successfully_mapped = sum(
            1 for mapping in self.user_mappings.values() if mapping.is_mapped
        )
        no_identifier = sum(
            1
            for mapping in self.user_mappings.values()
            if not mapping.legacy_email and not mapping.is_mapped
        )
        not_in_cloud = sum(
            1
            for mapping in self.user_mappings.values()
            if mapping.legacy_email and not mapping.is_mapped
        )

        logger.info("Successfully mapped: %s users", successfully_mapped)
        if no_identifier > 0:
            logger.info(
                "Unmapped (no %s): %s users", self.identifier_type, no_identifier
            )
        if not_in_cloud > 0:
            logger.info("Unmapped (not in Cloud): %s users", not_in_cloud)

    def _fetch_and_map_usergroups(self) -> None:
        """Fetch and map user groups from Cloud."""
        if not self.all_grantee_group_names:
            logger.info("----No user groups to fetch----")
            return

        logger.info("----Fetching Cloud user groups by name----")
        unique_group_names = list(self.all_grantee_group_names)
        cloud_usergroups = self.ctx.cloud_client.get_usergroups_by_names(
            unique_group_names
        )
        logger.info(
            "Retrieved %s Cloud user groups from organization",
            len(cloud_usergroups),
        )

        # Build map: name -> usergroup ID
        for usergroup in cloud_usergroups:
            usergroup_id = usergroup.get("id")
            # Get name from attributes (same structure as users)
            attributes = usergroup.get("attributes", {})
            usergroup_name = attributes.get("name")
            if usergroup_id and usergroup_name:
                self.cloud_usergroup_map[usergroup_name] = usergroup_id

        # Print mapping statistics
        successfully_mapped = len(self.cloud_usergroup_map)
        not_in_cloud = len(self.all_grantee_group_names) - successfully_mapped

        logger.info("\n----Mapping user groups----")
        logger.info("Successfully mapped: %s user groups", successfully_mapped)
        if not_in_cloud > 0:
            logger.info("Unmapped (not in Cloud): %s user groups", not_in_cloud)

            # Print which groups weren't found
            for group_name in self.all_grantee_group_names:
                if group_name not in self.cloud_usergroup_map:
                    logger.warning("  User group '%s' not found in Cloud", group_name)

    def _build_object_updates(self) -> tuple[list[ObjectUpdate], dict[str, int]]:
        """Build list of ObjectUpdate instances from dashboards."""
        logger.info("----Processing dashboards----")
        object_updates = []
        skip_stats = {
            "no_cloud_mapping": 0,
            "no_user_mapping": 0,
        }

        for idx, obj in enumerate(self.legacy_dashboards, start=1):
            update = self._process_single_dashboard(obj, idx, skip_stats)
            if update:
                object_updates.append(update)

        for objects, object_type, mappings in (
            (self.legacy_metrics, "metric", self.ctx.metric_mappings),
            (self.legacy_insights, "insight", self.ctx.insight_mappings),
        ):
            if objects:
                logger.info("----Processing %ss----", object_type)
            for obj in objects:
                update = self._process_creator_only(
                    obj, object_type, mappings, skip_stats
                )
                if update:
                    object_updates.append(update)

        return object_updates, skip_stats

    def _process_creator_only(
        self,
        obj: dict,
        object_type: str,
        mappings: IdMappings | None,
        skip_stats: dict[str, int],
    ) -> ObjectUpdate | None:
        """Build a creator/modifier-only update for a metric or an insight."""
        if not obj or len(obj) != 1 or mappings is None:
            return None
        root_obj = next(iter(obj.values()))
        if not isinstance(root_obj, dict) or "meta" not in root_obj:
            return None
        meta = root_obj["meta"]
        cloud_object_id = mappings.get_value_by_key(meta.get("identifier"))
        if not cloud_object_id:
            skip_stats["no_cloud_mapping"] += 1
            return None
        legacy_creator_id = self._extract_profile_id(meta.get("author"))
        cloud_creator_id, creator_email = self._get_mapped_user(legacy_creator_id)
        if not cloud_creator_id:
            skip_stats["no_user_mapping"] += 1
            logger.warning(
                "Creator '%s' not mapped for %s '%s' - skipped",
                creator_email or legacy_creator_id,
                object_type,
                meta.get("title", ""),
            )
            return None
        legacy_modifier_id = self._extract_profile_id(meta.get("contributor"))
        cloud_modifier_id, _ = self._get_mapped_user(legacy_modifier_id)
        return ObjectUpdate(
            legacy_object_id=meta.get("identifier"),
            legacy_object_title=meta.get("title", ""),
            cloud_object_id=cloud_object_id,
            object_type=object_type,
            legacy_creator_id=legacy_creator_id,
            legacy_modifier_id=legacy_modifier_id,
            cloud_creator_id=cloud_creator_id,
            cloud_modifier_id=cloud_modifier_id,
        )

    def _process_single_dashboard(
        self, obj: dict, idx: int, skip_stats: dict[str, int]
    ) -> ObjectUpdate | None:
        """Process a single dashboard object."""
        if not obj or len(obj) != 1:
            return None

        root_obj = next(iter(obj.values()))
        if not isinstance(root_obj, dict) or "meta" not in root_obj:
            return None

        dashboard_meta = root_obj["meta"]
        legacy_object_id = dashboard_meta.get("identifier")
        legacy_object_title = dashboard_meta.get("title", "")

        # Check Cloud mapping
        cloud_object_id = self.ctx.dashboard_mappings.get_value_by_key(legacy_object_id)
        if not cloud_object_id:
            skip_stats["no_cloud_mapping"] += 1
            return None

        # Extract and map creator
        creator_uri = dashboard_meta.get("author")
        legacy_creator_id = self._extract_profile_id(creator_uri)
        cloud_creator_id, creator_email = self._get_mapped_user(legacy_creator_id)
        legacy_modifier_id = self._extract_profile_id(dashboard_meta.get("contributor"))
        cloud_modifier_id, _ = self._get_mapped_user(legacy_modifier_id)

        # Process grantees if sharing is not skipped
        grantee_user_ids, grantee_mappings, grantee_group_ids, group_mappings = (
            self._process_dashboard_grantees(dashboard_meta, cloud_creator_id)
        )

        # Print processing status
        if self.ctx.print_user_mappings:
            self._print_dashboard_status(
                idx,
                legacy_object_title,
                creator_email,
                cloud_creator_id,
                grantee_mappings,
                group_mappings,
            )

        # Create update if we have a valid target object
        # If creator is missing, we still proceed (to sync permissions), but log a warning
        if not cloud_creator_id and not self.ctx.skip_creators:
            logger.warning(
                "Creator '%s' not mapped for dashboard '%s' - creator update will be skipped",
                creator_email or legacy_creator_id,
                legacy_object_title,
            )

        return ObjectUpdate(
            legacy_object_id=legacy_object_id,
            legacy_object_title=legacy_object_title,
            cloud_object_id=cloud_object_id,
            object_type="dashboard",
            legacy_creator_id=legacy_creator_id,
            legacy_modifier_id=legacy_modifier_id,
            cloud_creator_id=cloud_creator_id,
            cloud_modifier_id=cloud_modifier_id,
            grantee_user_ids=grantee_user_ids if grantee_user_ids else None,
            grantee_group_ids=grantee_group_ids if grantee_group_ids else None,
        )

    def _process_dashboard_grantees(
        self, dashboard_meta: dict, cloud_creator_id: str | None
    ) -> tuple[
        list[str], list[tuple[str, str | None]], list[str], list[tuple[str, str | None]]
    ]:
        """
        Process grantees for a single dashboard.

        Returns:
            tuple: (grantee_user_ids, grantee_user_mappings, grantee_group_ids, group_mappings)
        """
        grantee_user_ids = []
        grantee_mappings = []
        grantee_group_ids = []
        group_mappings = []

        # Process grantees if at least one type is not skipped
        if not self.ctx.skip_individual_grantees or not self.ctx.skip_group_grantees:
            uri = dashboard_meta.get("uri", "")
            numerical_id = uri.split("/")[-1] if uri else None
            if numerical_id:
                grantees_data = self.ctx.legacy_client.get_object_grantees(numerical_id)
                grantee_emails, grantee_group_names = self._extract_grantees(
                    grantees_data
                )

                # Process individual user grantees (if not skipped)
                if not self.ctx.skip_individual_grantees:
                    for email in grantee_emails:
                        cloud_user_id = self.cloud_user_map.get(email)
                        grantee_mappings.append((email, cloud_user_id))
                        if cloud_user_id:
                            grantee_user_ids.append(cloud_user_id)

                # Process user group grantees (if not skipped)
                if not self.ctx.skip_group_grantees:
                    for group_name in grantee_group_names:
                        cloud_group_id = self.cloud_usergroup_map.get(group_name)
                        group_mappings.append((group_name, cloud_group_id))
                        if cloud_group_id:
                            grantee_group_ids.append(cloud_group_id)

        return grantee_user_ids, grantee_mappings, grantee_group_ids, group_mappings

    def _extract_profile_id(self, uri: str | None) -> str | None:
        """Extract profile ID from Legacy URI."""
        if not uri:
            return None
        if uri.startswith("/gdc/account/profile/"):
            return uri.split("/")[-1]
        return uri

    def _get_mapped_user(
        self, legacy_user_id: str | None
    ) -> tuple[str | None, str | None]:
        """Get mapped Cloud user ID and email for a Legacy user."""
        if not legacy_user_id or legacy_user_id not in self.user_mappings:
            return None, None

        mapping = self.user_mappings[legacy_user_id]
        creator_email = mapping.legacy_email
        cloud_user_id = mapping.cloud_user_id if mapping.is_mapped else None

        return cloud_user_id, creator_email

    def _print_dashboard_status(
        self,
        idx: int,
        title: str,
        creator_email: str | None,
        cloud_creator_id: str | None,
        grantee_mappings: list[tuple[str, str | None]],
        group_mappings: list[tuple[str, str | None]],
    ) -> None:
        """Print processing status for a single dashboard."""
        # Print header line
        logger.info("Processing %s: %s", idx, title)

        # Print creator status (always EDIT permission, unless skipped)
        if not self.ctx.skip_creators:
            if creator_email:
                if cloud_creator_id:
                    logger.info(
                        "  Legacy creator '%s' mapped to Cloud user '%s' - granting EDIT permission",
                        creator_email,
                        cloud_creator_id,
                    )
                else:
                    logger.info(
                        "  Legacy creator '%s' not found in Cloud - skipping",
                        creator_email,
                    )
            else:
                logger.info("  No creator info - skipping")

        # Print individual user grantees status (if not skipped)
        if not self.ctx.skip_individual_grantees:
            for legacy_email, cloud_id in grantee_mappings:
                if cloud_id:
                    logger.info(
                        "  Legacy grantee '%s' mapped to Cloud user '%s' - granting %s permission",
                        legacy_email,
                        cloud_id,
                        self.ctx.permission_level,
                    )
                else:
                    logger.info(
                        "  Legacy grantee '%s' not found in Cloud - skipping",
                        legacy_email,
                    )

        # Print user group grantees status (if not skipped)
        if not self.ctx.skip_group_grantees:
            for group_name, cloud_group_id in group_mappings:
                if cloud_group_id:
                    logger.info(
                        "  Legacy group '%s' mapped to Cloud group '%s' - granting %s permission",
                        group_name,
                        cloud_group_id,
                        self.ctx.permission_level,
                    )
                else:
                    logger.info(
                        "  Legacy group '%s' not found in Cloud - skipping",
                        group_name,
                    )
