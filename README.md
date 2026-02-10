# yattmcp

Yet Another TickTick MCP -- an MCP server that gives AI agents full task management over TickTick, without exposing every API wart.

## Why this one?

Most TickTick MCP servers either mirror the raw API 1:1 (numeric priorities, bizarre date formats, internal fields like `sortOrder`) or go the other direction with 50+ "workflow" tools that bloat the tool list and confuse model selection. yattmcp takes a different approach:

**9 tools. Full CRUD. Agent-friendly abstractions.**

- **Normalized data** -- Priority is `"high"`, not `5`. Dates accept `"2025-03-15"` and get converted. `isAllDay` is auto-detected from your date format. Subtasks are `{title, isCompleted}`, not `{title, status: 0}`.
- **One composable search tool** -- Instead of separate `get_overdue_tasks`, `get_todays_tasks`, `get_high_priority_tasks` tools, there's a single `ticktick_search_tasks` with optional filters that compose with AND logic. Want overdue high-priority tasks? One call.
- **Honest about limitations** -- Tool descriptions tell the agent that completed tasks aren't retrievable, that complete is one-way, and that both `taskId` and `projectId` are needed (and why). No silent failures.
- **Tool annotations** -- Every tool declares `readOnlyHint`, `destructiveHint`, and `idempotentHint` so agents can reason about risk before calling.

## Authentication

yattmcp authenticates to the TickTick Open API using a token passed via the `TICKTICK_API_TOKEN` environment variable.

The easiest way to get a token is from TickTick directly: **Profile -> Settings -> Subscribe -> API Token**. This gives you a long-lived token that doesn't expire.

Alternatively, you can use an OAuth2 access token obtained through TickTick's [developer portal](https://developer.ticktick.com/manage), but you'll need to handle token refresh yourself -- yattmcp does not manage the OAuth2 lifecycle.

## Quick start

### With `uv` (recommended)

```bash
# Install and run
uvx yattmcp serve

# Or clone and run from source
git clone https://github.com/mjkoo/yattmcp.git
cd yattmcp
uv run yattmcp serve
```

### With Docker

```bash
docker run -e TICKTICK_API_TOKEN=your-token ghcr.io/mjkoo/yattmcp:latest
```

### Claude Desktop configuration

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "uvx",
      "args": ["yattmcp", "serve"],
      "env": {
        "TICKTICK_API_TOKEN": "your-token-here"
      }
    }
  }
}
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TICKTICK_API_TOKEN` | Yes | TickTick Open API bearer token |
| `TICKTICK_INBOX_PROJECT_ID` | No | Project ID for the Inbox (defaults to `"inbox"`). Set this so agents can create tasks without specifying a project. |

A `.env` file in the working directory is loaded automatically.

## Transport options

```bash
yattmcp serve                              # stdio (default, for Claude Desktop)
yattmcp serve --transport streamable-http  # HTTP streaming
yattmcp serve --transport sse              # Server-sent events
yattmcp serve --transport http             # Plain HTTP
yattmcp serve --host 0.0.0.0 --port 8080  # Bind to specific host/port
```

## The 9 tools

| Tool | Type | Description |
|---|---|---|
| `ticktick_list_projects` | Read | List all projects with IDs, names, colors, view modes. Entry point for most workflows. |
| `ticktick_get_project_tasks` | Read | Get all active tasks in a project. |
| `ticktick_get_task` | Read | Get full details of a single task by ID. |
| `ticktick_search_tasks` | Read | Search and filter across all projects -- by query, priority, date range, or project. |
| `ticktick_create_project` | Write | Create a project with name, color, and view mode. |
| `ticktick_delete_project` | Destructive | Permanently delete a project and all its tasks. |
| `ticktick_create_task` | Write | Create a task with title, priority, dates, subtasks. Flexible date formats auto-normalized. |
| `ticktick_update_task` | Write | Partial update -- only send fields you want to change. Fetches and merges automatically. |
| `ticktick_complete_task` | Write | Mark a task as done (one-way; the API has no uncomplete endpoint). |

## Development

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                  # Install dependencies
uv run pytest            # Run tests
uv run ruff check .      # Lint
uv run ruff format .     # Format
uv run mypy src/         # Type check (strict mode)
```