from typing import Annotated

import typer
from dotenv import load_dotenv

app = typer.Typer(name="yattmcp", help="Yet Another TickTick MCP server.")


@app.callback()
def main() -> None:
    """Yet Another TickTick MCP server."""


@app.command()
def serve(
    transport: Annotated[str, typer.Option(help="Transport to use.")] = "stdio",
) -> None:
    """Start the yattmcp MCP server."""
    load_dotenv()
    from yattmcp.server import mcp

    mcp.run(transport=transport)
