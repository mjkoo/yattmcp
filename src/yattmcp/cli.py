from enum import Enum
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv


class TransportType(str, Enum):
    stdio = "stdio"
    http = "http"
    sse = "sse"
    streamable_http = "streamable-http"


app = typer.Typer(name="yattmcp", help="Yet Another TickTick MCP server.")


@app.callback()
def main() -> None:
    """Yet Another TickTick MCP server."""


@app.command()
def serve(
    transport: Annotated[
        TransportType, typer.Option(help="Transport to use.")
    ] = TransportType.stdio,
    host: Annotated[Optional[str], typer.Option(help="Host to bind to.")] = None,
    port: Annotated[Optional[int], typer.Option(help="Port to bind to.")] = None,
) -> None:
    """Start the yattmcp MCP server."""
    load_dotenv()
    from yattmcp.server import mcp

    mcp.run(transport=transport.value, host=host, port=port)
