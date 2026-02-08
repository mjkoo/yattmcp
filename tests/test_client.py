"""Tests for yattmcp.client — async HTTP client with mocked transport."""

import httpx
import pytest

from yattmcp.client import TickTickClient


def _mock_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    content = b""
    if json_data is not None:
        import json

        content = json.dumps(json_data).encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://test"),
    )


class TestTickTickClientLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with TickTickClient("test-token") as client:
            assert client._client is not None
        assert client._client is None

    def test_client_property_without_context_raises(self) -> None:
        tc = TickTickClient("test-token")
        with pytest.raises(RuntimeError, match="async context manager"):
            _ = tc.client

    @pytest.mark.asyncio
    async def test_auth_header(self) -> None:
        async with TickTickClient("my-secret-token") as client:
            assert client.client.headers["authorization"] == "Bearer my-secret-token"


class TestTickTickClientProjects:
    @pytest.mark.asyncio
    async def test_list_projects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        projects = [{"id": "p1", "name": "Work"}]

        async def mock_get(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert url == "/project"
            return _mock_response(json_data=projects)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        async with TickTickClient("tok") as client:
            result = await client.list_projects()
        assert result == projects

    @pytest.mark.asyncio
    async def test_get_project_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = {"project": {"id": "p1", "name": "Work"}, "tasks": [], "columns": []}

        async def mock_get(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert "/project/p1/data" in url
            return _mock_response(json_data=data)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        async with TickTickClient("tok") as client:
            result = await client.get_project_data("p1")
        assert result == data

    @pytest.mark.asyncio
    async def test_create_project(self, monkeypatch: pytest.MonkeyPatch) -> None:
        created = {"id": "p2", "name": "New"}

        async def mock_post(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert url == "/project"
            return _mock_response(json_data=created)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        async with TickTickClient("tok") as client:
            result = await client.create_project({"name": "New"})
        assert result == created

    @pytest.mark.asyncio
    async def test_delete_project(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_delete(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert "/project/p1" in url
            return _mock_response(status_code=200)

        monkeypatch.setattr(httpx.AsyncClient, "delete", mock_delete)

        async with TickTickClient("tok") as client:
            await client.delete_project("p1")  # should not raise

    @pytest.mark.asyncio
    async def test_delete_project_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_delete(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            return _mock_response(status_code=404)

        monkeypatch.setattr(httpx.AsyncClient, "delete", mock_delete)

        async with TickTickClient("tok") as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.delete_project("bad-id")


class TestTickTickClientTasks:
    @pytest.mark.asyncio
    async def test_get_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        task = {"id": "t1", "title": "Do thing", "projectId": "p1"}

        async def mock_get(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert "/project/p1/task/t1" in url
            return _mock_response(json_data=task)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        async with TickTickClient("tok") as client:
            result = await client.get_task("p1", "t1")
        assert result == task

    @pytest.mark.asyncio
    async def test_create_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        created = {"id": "t2", "title": "New task"}

        async def mock_post(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert url == "/task"
            return _mock_response(json_data=created)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        async with TickTickClient("tok") as client:
            result = await client.create_task({"title": "New task", "projectId": "p1"})
        assert result == created

    @pytest.mark.asyncio
    async def test_update_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        updated = {"id": "t1", "title": "Updated"}

        async def mock_post(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert "/task/t1" in url
            return _mock_response(json_data=updated)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        async with TickTickClient("tok") as client:
            result = await client.update_task("t1", {"title": "Updated"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_complete_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_post(
            self_inner: httpx.AsyncClient, url: str, **kw: object
        ) -> httpx.Response:
            assert "/project/p1/task/t1/complete" in url
            return _mock_response(status_code=200)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        async with TickTickClient("tok") as client:
            await client.complete_task("p1", "t1")  # should not raise
