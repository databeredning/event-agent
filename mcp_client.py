from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from trace import trace_tool_call, trace_tool_result


SERVER = StdioServerParameters(
    command="/opt/event-agent/.venv/bin/python",
    args=["/opt/event-agent/server.py"],
    cwd="/opt/event-agent",
)


async def call_tool(name, arguments=None):
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            trace_tool_call(name, arguments or {})
            result = await session.call_tool(
                name,
                arguments=arguments or {},
            )

            trace_tool_result(result)
            return result
