"""CLI Entry point for running the Czech Elections 2026 MCP Server."""

import argparse
import asyncio
import sys

from src.config import settings


async def run_stdio():
    """Runs the MCP server over standard input/output (stdio)."""
    from mcp.server.stdio import stdio_server
    from src.parsers.codebook_loader import codebook_index
    from src.server import mcp_server

    codebook_index.initialize_defaults()
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


def main():
    """CLI parser and router."""
    parser = argparse.ArgumentParser(
        description="MCP Server pro Volby 2026 v ČR (Senát a zastupitelstva obcí)"
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Komunikační protokol: 'sse' (HTTP server pro Claude Code, ChatGPT, Antigravity) nebo 'stdio' (pro lokální CLI)",
    )
    parser.add_argument(
        "--host",
        default=settings.HOST,
        help=f"Host pro SSE server (výchozí: {settings.HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.PORT,
        help=f"Port pro SSE server (výchozí: {settings.PORT})",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        import uvicorn
        uvicorn.run("src.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
