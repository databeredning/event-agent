from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER = StdioServerParameters(
    command="/opt/event-agent/.venv/bin/python",
    args=["/opt/event-agent/server.py"],
    cwd="/opt/event-agent",
)


@asynccontextmanager
async def mcp_session():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session