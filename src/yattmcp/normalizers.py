"""Pure functions for normalizing between agent-friendly and TickTick API formats."""

from datetime import datetime, timezone
from typing import Any

# -- Priority --

_PRIORITY_TO_API: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 3,
    "high": 5,
}

_PRIORITY_FROM_API: dict[int, str] = {v: k for k, v in _PRIORITY_TO_API.items()}


def priority_to_api(priority: str) -> int:
    """Convert agent-friendly priority string to TickTick numeric priority.

    :param priority: One of "none", "low", "medium", "high".
    :returns: Numeric priority for the API (0, 1, 3, 5).
    :raises ValueError: If priority string is invalid.
    """
    key = priority.lower().strip()
    if key not in _PRIORITY_TO_API:
        raise ValueError(
            f"Invalid priority {priority!r}. "
            f"Must be one of: {', '.join(_PRIORITY_TO_API)}"
        )
    return _PRIORITY_TO_API[key]


def priority_from_api(priority: int) -> str:
    """Convert TickTick numeric priority to agent-friendly string.

    :param priority: Numeric priority from the API.
    :returns: One of "none", "low", "medium", "high".
    """
    return _PRIORITY_FROM_API.get(priority, "none")


# -- Dates --


def date_to_api(date_str: str) -> tuple[str, bool]:
    """Convert a flexible date string to TickTick's API format.

    Accepts:
    - "2025-03-15" (date only → midnight UTC, isAllDay=True)
    - "2025-03-15T14:00" or "2025-03-15T14:00:00" (naive → UTC)
    - Full ISO 8601 with offset

    :param date_str: Date string in any accepted format.
    :returns: Tuple of (TickTick date string, isAllDay flag).
    """
    dt = datetime.fromisoformat(date_str)

    # Date-only input: no time component was specified
    is_all_day = len(date_str) == 10  # "YYYY-MM-DD"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # TickTick format: yyyy-MM-dd'T'HH:mm:ss+0000 (no colon in tz offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z"), is_all_day


def date_from_api(date_str: str | None) -> str | None:
    """Convert TickTick's date format to standard ISO 8601.

    TickTick uses "+0000" (no colon); we normalize to "+00:00".

    :param date_str: Date string from TickTick API, or None.
    :returns: ISO 8601 date string, or None.
    """
    if not date_str:
        return None
    dt = datetime.fromisoformat(date_str)
    return dt.isoformat()


# -- Subtasks --


def subtask_to_api(subtask: dict[str, Any]) -> dict[str, Any]:
    """Convert agent-friendly subtask to TickTick API format.

    :param subtask: Dict with "title" and optional "isCompleted".
    :returns: Dict with "title" and "status" (0 or 1).
    """
    return {
        "title": subtask["title"],
        "status": 1 if subtask.get("isCompleted", False) else 0,
    }


def subtask_from_api(item: dict[str, Any]) -> dict[str, Any]:
    """Convert TickTick API subtask (item) to agent-friendly format.

    :param item: Dict from API with "title", "status", and "id".
    :returns: Dict with "id", "title", and "isCompleted".
    """
    return {
        "id": item.get("id"),
        "title": item.get("title", ""),
        "isCompleted": item.get("status", 0) != 0,
    }


# -- Task normalization (from API) --


def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw TickTick task dict to agent-friendly format.

    :param task: Raw task dict from the API.
    :returns: Normalized task dict.
    """
    result: dict[str, Any] = {
        "id": task["id"],
        "projectId": task.get("projectId", ""),
        "title": task.get("title", ""),
        "content": task.get("content", ""),
        "priority": priority_from_api(task.get("priority", 0)),
        "isCompleted": task.get("status", 0) != 0,
        "isAllDay": task.get("isAllDay", False),
    }

    for date_field in ("dueDate", "startDate"):
        result[date_field] = date_from_api(task.get(date_field))

    items = task.get("items")
    if items:
        result["subtasks"] = [subtask_from_api(item) for item in items]
    else:
        result["subtasks"] = []

    return result


# -- Project normalization (from API) --


def normalize_project(project: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw TickTick project dict to agent-friendly format.

    :param project: Raw project dict from the API.
    :returns: Normalized project dict.
    """
    return {
        "id": project["id"],
        "name": project.get("name", ""),
        "color": project.get("color"),
        "viewMode": project.get("viewMode"),
        "isClosed": project.get("closed", False),
    }
