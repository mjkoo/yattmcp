"""Async HTTP client for the TickTick Open API."""

from typing import Self

import httpx


class TickTickClient:
    """Wraps the TickTick Open API with async HTTP methods.

    Use as an async context manager to manage the underlying httpx client.
    Does NOT normalize responses — returns raw API dicts.
    """

    BASE_URL = "https://api.ticktick.com/open/v1"

    def __init__(self, api_token: str) -> None:
        self._api_token = api_token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self._api_token}"},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("TickTickClient must be used as an async context manager")
        return self._client

    # -- Projects --

    async def list_projects(self) -> list[dict]:
        """GET /project — list all projects."""
        resp = await self.client.get("/project")
        resp.raise_for_status()
        return resp.json()

    async def get_project_data(self, project_id: str) -> dict:
        """GET /project/{id}/data — get project with tasks and columns."""
        resp = await self.client.get(f"/project/{project_id}/data")
        resp.raise_for_status()
        return resp.json()

    async def create_project(self, data: dict) -> dict:
        """POST /project — create a new project."""
        resp = await self.client.post("/project", json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete_project(self, project_id: str) -> None:
        """DELETE /project/{id} — permanently delete a project."""
        resp = await self.client.delete(f"/project/{project_id}")
        resp.raise_for_status()

    # -- Tasks --

    async def get_task(self, project_id: str, task_id: str) -> dict:
        """GET /project/{pid}/task/{tid} — get a single task."""
        resp = await self.client.get(f"/project/{project_id}/task/{task_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_task(self, data: dict) -> dict:
        """POST /task — create a new task."""
        resp = await self.client.post("/task", json=data)
        resp.raise_for_status()
        return resp.json()

    async def update_task(self, task_id: str, data: dict) -> dict:
        """POST /task/{id} — update an existing task."""
        resp = await self.client.post(f"/task/{task_id}", json=data)
        resp.raise_for_status()
        return resp.json()

    async def complete_task(self, project_id: str, task_id: str) -> None:
        """POST /project/{pid}/task/{tid}/complete — mark task as done."""
        resp = await self.client.post(
            f"/project/{project_id}/task/{task_id}/complete"
        )
        resp.raise_for_status()
