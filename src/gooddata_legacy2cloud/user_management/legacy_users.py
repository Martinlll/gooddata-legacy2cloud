# (C) 2026 GoodData Corporation


def extract_creator_modifier_ids(objects: list[dict]) -> set[str]:
    """
    Extracts unique creator and modifier user IDs from Legacy objects.

    Args:
        objects: List of Legacy objects (dashboards, insights, etc.)

    Returns:
        set: A set of unique Legacy user profile IDs (without /gdc/account/profile/ prefix)
    """
    user_ids: set[str] = set()

    for obj in objects:
        # Get the first (and only) root object
        if obj and len(obj) == 1:
            root_obj = next(iter(obj.values()))
            if isinstance(root_obj, dict) and "meta" in root_obj:
                obj_meta = root_obj["meta"]

                # Extract creator ID from author field
                author = obj_meta.get("author")
                if author:
                    # Extract ID from URI like /gdc/account/profile/USER_ID
                    if author.startswith("/gdc/account/profile/"):
                        creator_id = author.split("/")[-1]
                    else:
                        creator_id = author
                    if creator_id:
                        user_ids.add(creator_id)

                # Extract modifier ID (Bear `contributor` = last modifier)
                modifier = obj_meta.get("contributor") or obj_meta.get("createdBy")
                if modifier:
                    # Extract ID from URI like /gdc/account/profile/USER_ID
                    if modifier.startswith("/gdc/account/profile/"):
                        modifier_id = modifier.split("/")[-1]
                    else:
                        modifier_id = modifier
                    if modifier_id:
                        user_ids.add(modifier_id)

    return user_ids


def build_legacy_user_email_map(
    users: list[dict], identifier_type: str = "login"
) -> dict[str, str]:
    """
    Builds a mapping from Legacy user profile IDs to email addresses or login names.

    Args:
        users: List of Legacy user dictionaries
        identifier_type: Field to use as identifier - either "email" or "login" (default: "login")

    Returns:
        dict: A dictionary mapping user profile ID to email/login
    """
    user_map: dict[str, str] = {}

    for user_wrapper in users:
        user_data = user_wrapper.get("user", {})

        # Extract profile ID from the profile link
        profile_link = user_data.get("links", {}).get("self", "")
        if profile_link:
            profile_id = profile_link.split("/")[-1]
        else:
            continue

        # Get the identifier field (email or login)
        content = user_data.get("content", {})
        identifier = content.get(identifier_type)

        if identifier:
            user_map[profile_id] = identifier.lower()  # Store lowercase for comparison

    return user_map
