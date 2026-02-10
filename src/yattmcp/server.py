"""TickTick MCP server — 9 tools wrapping the TickTick Open API."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.dependencies import CurrentFastMCP, Depends
from mcp.types import ToolAnnotations

from yattmcp.client import TickTickClient
from yattmcp.normalizers import (
    date_to_api,
    normalize_project,
    normalize_task,
    priority_to_api,
    subtask_to_api,
)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage the TickTickClient lifecycle."""
    api_token = os.environ["TICKTICK_API_TOKEN"]
    inbox_project_id = os.environ.get("TICKTICK_INBOX_PROJECT_ID", "inbox")
    async with TickTickClient(api_token) as client:
        yield {"client": client, "inbox_project_id": inbox_project_id}


mcp = FastMCP("yattmcp", lifespan=lifespan)


async def get_client(
    server: FastMCP = CurrentFastMCP(),  # type: ignore[no-untyped-call]
) -> TickTickClient:
    return server._lifespan_result["client"]  # type: ignore[index,no-any-return]


async def get_inbox_id(
    server: FastMCP = CurrentFastMCP(),  # type: ignore[no-untyped-call]
) -> str | None:
    return server._lifespan_result["inbox_project_id"]  # type: ignore[index,no-any-return]


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


def _ok(data: Any) -> str:
    return json.dumps(data, default=str)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
async def ticktick_list_projects(
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
    inbox_id: str | None = Depends(get_inbox_id),  # type: ignore[arg-type]
) -> str:
    """List all TickTick projects (lists).

    Returns each project's id, name, color, viewMode, and isClosed status.
    Use the project id when calling other tools that require a projectId.
    """
    try:
        projects = await client.list_projects()
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to list projects: {e.response.status_code}")

    result = [normalize_project(p) for p in projects]

    if inbox_id:
        inbox_entry = {
            "id": inbox_id,
            "name": "Inbox",
            "color": None,
            "viewMode": None,
            "isClosed": False,
        }
        result.insert(0, inbox_entry)

    return _ok(result)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
async def ticktick_get_project_tasks(
    project_id: str,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    """Get all active (uncompleted) tasks in a project.

    Note: The TickTick API only returns uncompleted tasks from this endpoint.
    Completed tasks are not available.

    :param project_id: The project ID. Call ticktick_list_projects first to get this.
    """
    try:
        data = await client.get_project_data(project_id)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to get project tasks: {e.response.status_code}")

    tasks = data.get("tasks", [])
    return _ok([normalize_task(t) for t in tasks])


@mcp.tool(
    annotations=ToolAnnotations(destructiveHint=False),
)
async def ticktick_create_project(
    name: str,
    color: str | None = None,
    view_mode: str | None = None,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    """Create a new TickTick project (list).

    :param name: Project name (required).
    :param color: Hex color string like "#F18181" (optional).
    :param view_mode: One of "list", "kanban", or "timeline" (optional).
    """
    payload: dict[str, Any] = {"name": name}
    if color is not None:
        payload["color"] = color
    if view_mode is not None:
        payload["viewMode"] = view_mode

    try:
        result = await client.create_project(payload)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to create project: {e.response.status_code}")

    return _ok(normalize_project(result))


@mcp.tool(
    annotations=ToolAnnotations(destructiveHint=True),
)
async def ticktick_delete_project(
    project_id: str,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    """Permanently delete a TickTick project and ALL its tasks.

    This action is irreversible. Use with caution.

    :param project_id: The project ID to delete.
    """
    try:
        await client.delete_project(project_id)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to delete project: {e.response.status_code}")

    return _ok({"deleted": True, "projectId": project_id})


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
async def ticktick_get_task(
    project_id: str,
    task_id: str,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    """Get full details of a single task.

    Both projectId and taskId are required because the TickTick API scopes
    tasks under projects, even though task IDs are globally unique.

    :param project_id: The project this task belongs to.
    :param task_id: The task ID.
    """
    try:
        task = await client.get_task(project_id, task_id)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to get task: {e.response.status_code}")

    return _ok(normalize_task(task))


@mcp.tool(
    annotations=ToolAnnotations(destructiveHint=False),
)
async def ticktick_create_task(
    title: str,
    project_id: str | None = None,
    content: str | None = None,
    priority: str = "none",
    due_date: str | None = None,
    start_date: str | None = None,
    is_all_day: bool | None = None,
    subtasks: list[dict[str, Any]] | None = None,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
    inbox_id: str | None = Depends(get_inbox_id),  # type: ignore[arg-type]
) -> str:
    """Create a new task in TickTick.

    Warning: Backslashes and literal \\n in the content field may silently
    break TickTick sync. Prefer plain text.

    :param title: Task title (required).
    :param project_id: Project to create the task in. If omitted, uses the
        Inbox project (if configured). Call ticktick_list_projects to get IDs.
    :param content: Task description/notes (optional).
    :param priority: "none", "low", "medium", or "high" (default: "none").
    :param due_date: Due date — accepts "2025-03-15", "2025-03-15T14:00",
        or full ISO 8601 with offset (optional).
    :param start_date: Start date, same formats as due_date (optional).
    :param is_all_day: Whether this is an all-day task. Auto-detected from
        date format if not set explicitly.
    :param subtasks: List of subtasks, each with "title" (required) and
        "isCompleted" (optional bool, default false).
    """
    resolved_project_id = project_id or inbox_id
    if not resolved_project_id:
        return _error(
            "No project_id provided and no Inbox project configured. "
            "Call ticktick_list_projects first to get a project ID."
        )

    try:
        api_priority = priority_to_api(priority)
    except ValueError as e:
        return _error(str(e))

    payload: dict[str, Any] = {
        "title": title,
        "projectId": resolved_project_id,
        "priority": api_priority,
    }

    if content is not None:
        payload["content"] = content

    all_day = is_all_day

    if due_date is not None:
        try:
            api_date, date_is_all_day = date_to_api(due_date)
            payload["dueDate"] = api_date
            if all_day is None:
                all_day = date_is_all_day
        except ValueError:
            return _error(f"Invalid due_date format: {due_date!r}")

    if start_date is not None:
        try:
            api_date, date_is_all_day = date_to_api(start_date)
            payload["startDate"] = api_date
            if all_day is None:
                all_day = date_is_all_day
        except ValueError:
            return _error(f"Invalid start_date format: {start_date!r}")

    if all_day is not None:
        payload["isAllDay"] = all_day

    if subtasks:
        payload["items"] = [subtask_to_api(s) for s in subtasks]

    try:
        result = await client.create_task(payload)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to create task: {e.response.status_code}")

    return _ok(normalize_task(result))


@mcp.tool(
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True),
)
async def ticktick_update_task(
    task_id: str,
    project_id: str,
    title: str | None = None,
    content: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    start_date: str | None = None,
    is_all_day: bool | None = None,
    subtasks: list[dict[str, Any]] | None = None,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    """Update an existing task. Only include fields you want to change.

    Fetches the current task first, merges your changes, then sends the update.

    :param task_id: The task ID to update.
    :param project_id: The project this task belongs to.
    :param title: New title (optional).
    :param content: New description/notes (optional).
    :param priority: New priority — "none", "low", "medium", "high" (optional).
    :param due_date: New due date (optional). Same flexible formats as create.
    :param start_date: New start date (optional).
    :param is_all_day: Whether this is an all-day task (optional).
    :param subtasks: Replacement subtask list (optional). Each subtask needs
        "title" and optionally "isCompleted".
    """
    # Fetch existing task to merge with
    try:
        existing = await client.get_task(project_id, task_id)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to fetch task for update: {e.response.status_code}")

    if title is not None:
        existing["title"] = title
    if content is not None:
        existing["content"] = content

    if priority is not None:
        try:
            existing["priority"] = priority_to_api(priority)
        except ValueError as e:
            return _error(str(e))

    all_day = is_all_day

    if due_date is not None:
        try:
            api_date, date_is_all_day = date_to_api(due_date)
            existing["dueDate"] = api_date
            if all_day is None:
                all_day = date_is_all_day
        except ValueError:
            return _error(f"Invalid due_date format: {due_date!r}")

    if start_date is not None:
        try:
            api_date, date_is_all_day = date_to_api(start_date)
            existing["startDate"] = api_date
            if all_day is None:
                all_day = date_is_all_day
        except ValueError:
            return _error(f"Invalid start_date format: {start_date!r}")

    if all_day is not None:
        existing["isAllDay"] = all_day

    if subtasks is not None:
        existing["items"] = [subtask_to_api(s) for s in subtasks]

    try:
        result = await client.update_task(task_id, existing)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to update task: {e.response.status_code}")

    return _ok(normalize_task(result))


@mcp.tool(
    annotations=ToolAnnotations(destructiveHint=False),
)
async def ticktick_complete_task(
    task_id: str,
    project_id: str,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    """Mark a task as completed.

    This is a one-way operation — the TickTick Open API does not provide
    an endpoint to uncomplete a task.

    :param task_id: The task ID to complete.
    :param project_id: The project this task belongs to.
    """
    try:
        await client.complete_task(project_id, task_id)
    except httpx.HTTPStatusError as e:
        return _error(f"Failed to complete task: {e.response.status_code}")

    return _ok({"completed": True, "taskId": task_id})


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
async def ticktick_search_tasks(
    query: str | None = None,
    project_id: str | None = None,
    priority: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    client: TickTickClient = Depends(get_client),  # type: ignore[arg-type]
    inbox_id: str | None = Depends(get_inbox_id),  # type: ignore[arg-type]
) -> str:
    """Search and filter tasks across projects.

    All filters are optional and combine with AND logic. Since TickTick has
    no server-side search API, this fetches tasks from projects and filters
    locally.

    Note: Only uncompleted tasks are available from the TickTick API.

    :param query: Case-insensitive substring search on title and content.
    :param project_id: Limit search to a single project (optimization).
    :param priority: Filter by priority — "none", "low", "medium", "high".
    :param due_before: Only tasks due before this date (ISO 8601 or "YYYY-MM-DD").
    :param due_after: Only tasks due after this date (ISO 8601 or "YYYY-MM-DD").
    """
    # Determine which projects to search
    if project_id:
        project_ids = [project_id]
    else:
        try:
            projects = await client.list_projects()
        except httpx.HTTPStatusError as e:
            return _error(f"Failed to list projects: {e.response.status_code}")
        project_ids = [p["id"] for p in projects]
        if inbox_id:
            project_ids.append(inbox_id)

    # Parse date filters
    dt_before: datetime | None = None
    dt_after: datetime | None = None
    if due_before:
        try:
            dt_before = datetime.fromisoformat(due_before)
            if dt_before.tzinfo is None:
                dt_before = dt_before.replace(tzinfo=timezone.utc)
        except ValueError:
            return _error(f"Invalid due_before format: {due_before!r}")
    if due_after:
        try:
            dt_after = datetime.fromisoformat(due_after)
            if dt_after.tzinfo is None:
                dt_after = dt_after.replace(tzinfo=timezone.utc)
        except ValueError:
            return _error(f"Invalid due_after format: {due_after!r}")

    # Validate priority filter
    target_priority: str | None = None
    if priority:
        target_priority = priority.lower().strip()
        if target_priority not in ("none", "low", "medium", "high"):
            return _error(
                f"Invalid priority filter {priority!r}. "
                "Must be one of: none, low, medium, high"
            )

    # Fetch and filter
    all_tasks: list[dict[str, Any]] = []
    for pid in project_ids:
        try:
            data = await client.get_project_data(pid)
        except httpx.HTTPStatusError:
            continue  # skip inaccessible projects
        tasks = data.get("tasks", [])
        for task in tasks:
            normalized = normalize_task(task)

            # Apply filters
            if query:
                q = query.lower()
                title = (normalized.get("title") or "").lower()
                content = (normalized.get("content") or "").lower()
                if q not in title and q not in content:
                    continue

            if target_priority and normalized["priority"] != target_priority:
                continue

            if dt_before or dt_after:
                due_str = normalized.get("dueDate")
                if not due_str:
                    continue  # no due date → excluded by date filters
                task_due = datetime.fromisoformat(due_str)
                if dt_before and task_due >= dt_before:
                    continue
                if dt_after and task_due <= dt_after:
                    continue

            all_tasks.append(normalized)

    return _ok(all_tasks)
