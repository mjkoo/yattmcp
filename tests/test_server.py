"""Tests for yattmcp.server — tool logic with mocked TickTickClient."""

import copy
import json
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from yattmcp import server as _server

# FastMCP's @mcp.tool wraps functions in FunctionTool objects.
# Access the raw async function via .fn for direct unit testing.
ticktick_complete_task = _server.ticktick_complete_task.fn
ticktick_create_project = _server.ticktick_create_project.fn
ticktick_create_task = _server.ticktick_create_task.fn
ticktick_delete_project = _server.ticktick_delete_project.fn
ticktick_get_project_tasks = _server.ticktick_get_project_tasks.fn
ticktick_get_task = _server.ticktick_get_task.fn
ticktick_list_projects = _server.ticktick_list_projects.fn
ticktick_search_tasks = _server.ticktick_search_tasks.fn
ticktick_update_task = _server.ticktick_update_task.fn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RAW_PROJECT: dict[str, Any] = {
    "id": "p1",
    "name": "Work",
    "color": "#FF0000",
    "sortOrder": 0,
    "closed": False,
    "groupId": "",
    "viewMode": "list",
    "permission": "write",
    "kind": "TASK",
}

RAW_TASK: dict[str, Any] = {
    "id": "t1",
    "projectId": "p1",
    "title": "Buy groceries",
    "content": "Milk and eggs",
    "desc": "",
    "priority": 5,
    "status": 0,
    "isAllDay": False,
    "dueDate": "2025-03-15T00:00:00+0000",
    "startDate": "2025-03-14T00:00:00+0000",
    "timeZone": "UTC",
    "kind": "CHECKLIST",
    "sortOrder": 12345,
    "items": [
        {"id": "s1", "title": "Milk", "status": 0, "sortOrder": 0},
        {"id": "s2", "title": "Eggs", "status": 1, "sortOrder": 1, "completedTime": "2025-03-14T10:00:00+0000"},
    ],
}

RAW_PROJECT_DATA: dict[str, Any] = {
    "project": RAW_PROJECT,
    "tasks": [RAW_TASK],
    "columns": [],
}


def _make_client(**overrides: Any) -> AsyncMock:
    """Create a mock TickTickClient with sensible defaults.

    Deep-copies default fixtures so tests that mutate dicts (e.g. update_task)
    don't pollute other tests.
    """
    client = AsyncMock()
    client.list_projects = AsyncMock(
        return_value=copy.deepcopy(overrides.get("projects", [RAW_PROJECT]))
    )
    client.get_project_data = AsyncMock(
        return_value=copy.deepcopy(overrides.get("project_data", RAW_PROJECT_DATA))
    )
    client.create_project = AsyncMock(
        return_value=copy.deepcopy(overrides.get("created_project", RAW_PROJECT))
    )
    client.delete_project = AsyncMock(return_value=None)
    client.get_task = AsyncMock(
        return_value=copy.deepcopy(overrides.get("task", RAW_TASK))
    )
    client.create_task = AsyncMock(
        return_value=copy.deepcopy(overrides.get("created_task", RAW_TASK))
    )
    client.update_task = AsyncMock(
        return_value=copy.deepcopy(overrides.get("updated_task", RAW_TASK))
    )
    client.complete_task = AsyncMock(return_value=None)
    return client


def _parse(result: str) -> Any:
    return json.loads(result)


def _http_error(status_code: int = 404) -> httpx.HTTPStatusError:
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://test"),
    )
    return httpx.HTTPStatusError("error", request=resp.request, response=resp)


# ---------------------------------------------------------------------------
# ticktick_list_projects
# ---------------------------------------------------------------------------


class TestListProjects:
    @pytest.mark.asyncio
    async def test_returns_normalized_projects(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_list_projects(client=client, inbox_id=None))
        assert len(result) == 1
        assert result[0]["id"] == "p1"
        assert result[0]["isClosed"] is False
        assert "closed" not in result[0]

    @pytest.mark.asyncio
    async def test_prepends_inbox(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_list_projects(client=client, inbox_id="inbox"))
        assert len(result) == 2
        assert result[0]["id"] == "inbox"
        assert result[0]["name"] == "Inbox"
        assert result[1]["id"] == "p1"

    @pytest.mark.asyncio
    async def test_no_inbox_when_none(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_list_projects(client=client, inbox_id=None))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        client = _make_client()
        client.list_projects.side_effect = _http_error(500)
        result = _parse(await ticktick_list_projects(client=client, inbox_id=None))
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_get_project_tasks
# ---------------------------------------------------------------------------


class TestGetProjectTasks:
    @pytest.mark.asyncio
    async def test_returns_normalized_tasks(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_get_project_tasks(project_id="p1", client=client))
        assert len(result) == 1
        assert result[0]["priority"] == "high"
        assert result[0]["subtasks"][1]["isCompleted"] is True

    @pytest.mark.asyncio
    async def test_empty_project(self) -> None:
        client = _make_client(project_data={"project": RAW_PROJECT, "tasks": [], "columns": []})
        result = _parse(await ticktick_get_project_tasks(project_id="p1", client=client))
        assert result == []

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        client = _make_client()
        client.get_project_data.side_effect = _http_error(404)
        result = _parse(await ticktick_get_project_tasks(project_id="bad", client=client))
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_create_project
# ---------------------------------------------------------------------------


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_basic_create(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_create_project(name="Work", client=client))
        assert result["id"] == "p1"
        client.create_project.assert_called_once_with({"name": "Work"})

    @pytest.mark.asyncio
    async def test_with_options(self) -> None:
        client = _make_client()
        await ticktick_create_project(
            name="Test", color="#FF0000", view_mode="kanban", client=client
        )
        client.create_project.assert_called_once_with(
            {"name": "Test", "color": "#FF0000", "viewMode": "kanban"}
        )

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        client = _make_client()
        client.create_project.side_effect = _http_error(400)
        result = _parse(await ticktick_create_project(name="Bad", client=client))
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_delete_project
# ---------------------------------------------------------------------------


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_delete_project(project_id="p1", client=client))
        assert result["deleted"] is True
        client.delete_project.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        client = _make_client()
        client.delete_project.side_effect = _http_error(404)
        result = _parse(await ticktick_delete_project(project_id="bad", client=client))
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_get_task
# ---------------------------------------------------------------------------


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_normalized(self) -> None:
        client = _make_client()
        result = _parse(await ticktick_get_task(project_id="p1", task_id="t1", client=client))
        assert result["id"] == "t1"
        assert result["priority"] == "high"
        client.get_task.assert_called_once_with("p1", "t1")

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        client = _make_client()
        client.get_task.side_effect = _http_error(404)
        result = _parse(await ticktick_get_task(project_id="p1", task_id="bad", client=client))
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_create_task
# ---------------------------------------------------------------------------


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_minimal_with_project_id(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_create_task(
                title="Test", project_id="p1", client=client, inbox_id=None
            )
        )
        assert result["id"] == "t1"
        call_payload = client.create_task.call_args[0][0]
        assert call_payload["title"] == "Test"
        assert call_payload["projectId"] == "p1"
        assert call_payload["priority"] == 0

    @pytest.mark.asyncio
    async def test_defaults_to_inbox(self) -> None:
        client = _make_client()
        await ticktick_create_task(title="Test", client=client, inbox_id="inbox")
        call_payload = client.create_task.call_args[0][0]
        assert call_payload["projectId"] == "inbox"

    @pytest.mark.asyncio
    async def test_no_project_no_inbox_errors(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_create_task(title="Test", client=client, inbox_id=None)
        )
        assert "error" in result
        assert "project_id" in result["error"]

    @pytest.mark.asyncio
    async def test_priority_conversion(self) -> None:
        client = _make_client()
        await ticktick_create_task(
            title="Test", project_id="p1", priority="high", client=client, inbox_id=None
        )
        call_payload = client.create_task.call_args[0][0]
        assert call_payload["priority"] == 5

    @pytest.mark.asyncio
    async def test_invalid_priority(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_create_task(
                title="Test", project_id="p1", priority="urgent",
                client=client, inbox_id=None,
            )
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_due_date_conversion(self) -> None:
        client = _make_client()
        await ticktick_create_task(
            title="Test", project_id="p1", due_date="2025-03-15",
            client=client, inbox_id=None,
        )
        call_payload = client.create_task.call_args[0][0]
        assert "2025-03-15" in call_payload["dueDate"]
        assert call_payload["isAllDay"] is True

    @pytest.mark.asyncio
    async def test_due_date_with_time(self) -> None:
        client = _make_client()
        await ticktick_create_task(
            title="Test", project_id="p1", due_date="2025-03-15T14:00",
            client=client, inbox_id=None,
        )
        call_payload = client.create_task.call_args[0][0]
        assert call_payload["isAllDay"] is False

    @pytest.mark.asyncio
    async def test_explicit_is_all_day_overrides(self) -> None:
        client = _make_client()
        await ticktick_create_task(
            title="Test", project_id="p1", due_date="2025-03-15",
            is_all_day=False, client=client, inbox_id=None,
        )
        call_payload = client.create_task.call_args[0][0]
        assert call_payload["isAllDay"] is False

    @pytest.mark.asyncio
    async def test_subtasks(self) -> None:
        client = _make_client()
        await ticktick_create_task(
            title="Test", project_id="p1",
            subtasks=[
                {"title": "Sub A"},
                {"title": "Sub B", "isCompleted": True},
            ],
            client=client, inbox_id=None,
        )
        call_payload = client.create_task.call_args[0][0]
        assert call_payload["items"] == [
            {"title": "Sub A", "status": 0},
            {"title": "Sub B", "status": 1},
        ]

    @pytest.mark.asyncio
    async def test_invalid_due_date(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_create_task(
                title="Test", project_id="p1", due_date="nope",
                client=client, inbox_id=None,
            )
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_update_task
# ---------------------------------------------------------------------------


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_merges_title(self) -> None:
        client = _make_client()
        await ticktick_update_task(
            task_id="t1", project_id="p1", title="New title", client=client
        )
        call_payload = client.update_task.call_args[0][1]
        assert call_payload["title"] == "New title"
        # Other fields preserved from fetched task
        assert call_payload["id"] == "t1"

    @pytest.mark.asyncio
    async def test_merges_priority(self) -> None:
        client = _make_client()
        await ticktick_update_task(
            task_id="t1", project_id="p1", priority="low", client=client
        )
        call_payload = client.update_task.call_args[0][1]
        assert call_payload["priority"] == 1

    @pytest.mark.asyncio
    async def test_invalid_priority(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_update_task(
                task_id="t1", project_id="p1", priority="critical", client=client
            )
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fetch_error(self) -> None:
        client = _make_client()
        client.get_task.side_effect = _http_error(404)
        result = _parse(
            await ticktick_update_task(task_id="bad", project_id="p1", client=client)
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_subtasks(self) -> None:
        client = _make_client()
        await ticktick_update_task(
            task_id="t1", project_id="p1",
            subtasks=[{"title": "New sub"}],
            client=client,
        )
        call_payload = client.update_task.call_args[0][1]
        assert call_payload["items"] == [{"title": "New sub", "status": 0}]


# ---------------------------------------------------------------------------
# ticktick_complete_task
# ---------------------------------------------------------------------------


class TestCompleteTask:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_complete_task(task_id="t1", project_id="p1", client=client)
        )
        assert result["completed"] is True
        assert result["taskId"] == "t1"
        client.complete_task.assert_called_once_with("p1", "t1")

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        client = _make_client()
        client.complete_task.side_effect = _http_error(404)
        result = _parse(
            await ticktick_complete_task(task_id="bad", project_id="p1", client=client)
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# ticktick_search_tasks
# ---------------------------------------------------------------------------


class TestSearchTasks:
    @pytest.mark.asyncio
    async def test_no_filters_returns_all(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(client=client, inbox_id=None)
        )
        assert len(result) == 1
        assert result[0]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_scoped_to_project(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(project_id="p1", client=client, inbox_id=None)
        )
        assert len(result) == 1
        # Should NOT have called list_projects when project_id given
        client.list_projects.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_filter_title(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                query="groceries", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_filter_content(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                query="Milk", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_filter_no_match(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                query="zzzzz", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_priority_filter(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                priority="high", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_priority_filter_no_match(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                priority="low", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_due_before_filter(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                due_before="2025-04-01", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_due_before_filter_excludes(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                due_before="2025-01-01", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_due_after_filter(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                due_after="2025-01-01", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_due_after_filter_excludes(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                due_after="2025-12-01", project_id="p1", client=client, inbox_id=None
            )
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_invalid_priority_filter(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(priority="urgent", client=client, inbox_id=None)
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_due_before(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(due_before="nope", client=client, inbox_id=None)
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_includes_inbox_when_searching_all(self) -> None:
        client = _make_client()
        await ticktick_search_tasks(client=client, inbox_id="inbox")
        # Should have fetched both the regular project and inbox
        pids = [call.args[0] for call in client.get_project_data.call_args_list]
        assert "inbox" in pids
        assert "p1" in pids

    @pytest.mark.asyncio
    async def test_combined_filters(self) -> None:
        client = _make_client()
        result = _parse(
            await ticktick_search_tasks(
                query="groceries",
                priority="high",
                due_before="2025-04-01",
                due_after="2025-01-01",
                project_id="p1",
                client=client,
                inbox_id=None,
            )
        )
        assert len(result) == 1
