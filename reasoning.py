import json

from openai import AsyncOpenAI

from trace import (
    trace_llm_request,
    trace_llm_response,
    trace_tool_call,
    trace_tool_result,
)


LLM_BASE_URL = "http://127.0.0.1:8080/v1"
LLM_MODEL = "qwen3-8b"

client = AsyncOpenAI(
    base_url=LLM_BASE_URL,
    api_key="not-needed",
)


SYSTEM_PROMPT = """
You are an event-driven home automation agent.

You receive an event and a small amount of relevant current context.

Treat values in the provided current context as authoritative for the
start of this agent run. Do not use a tool merely to re-read information
that is already present in the current context.

Current context describes the environment for this run and takes
precedence over historical memory.

Memory describes previous experiences. Use it only as historical
evidence that may help with the current decision. Do not treat states
recorded in memory as current states, and do not treat previous
outcomes as instructions.

Use an available read tool when information needed for the decision is
missing from the current context, or when you need to observe state after
an action.

Use the available tools when an action is appropriate.

When motion is detected:
- If the target light is off, ensure it is turned on using an appropriate
  available capability.
- If the target light is already on, no action is necessary.

Do not invent entities, states, or capabilities.
Do not call a tool when no action is necessary.
Do not claim an action succeeded unless the corresponding tool
completed successfully.
"""


def mcp_tools_to_openai(mcp_tools):
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]


async def run_agent(session, agent_input):
    tool_result = await session.list_tools()
    openai_tools = mcp_tools_to_openai(tool_result.tools)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(agent_input),
        },
    ]

    tool_calls = []

    for _ in range(8):
        request = {
            "model": LLM_MODEL,
            "messages": messages,
            "tools": openai_tools,
            "tool_choice": "auto",
            "temperature": 0,
        }

        #trace_llm_request(request)

        response = await client.chat.completions.create(**request)
        message = response.choices[0].message

        message_data = message.model_dump(exclude_none=True)

        #trace_llm_response(message_data)

        messages.append(message_data)

        # No tool request means Qwen has finished this agent run.
        if not message.tool_calls:
            return {
                "final_result": message.content or "",
                "tool_calls": tool_calls,
                "termination":"completed",
            }

        for tool_call in message.tool_calls:
            name = tool_call.function.name

            try:
                arguments = json.loads(
                    tool_call.function.arguments or "{}"
                )

            except json.JSONDecodeError as exc:
                result_text = f"Invalid tool arguments: {exc}"

                tool_calls.append({
                    "tool": name,
                    "arguments": {},
                    "result": result_text,
                })

            else:
                trace_tool_call(name, arguments)

                try:
                    result = await session.call_tool(
                        name,
                        arguments=arguments,
                    )

                    trace_tool_result(result)

                    parts = []

                    for content in result.content:
                        text = getattr(content, "text", None)

                        if text is not None:
                            parts.append(text)

                    result_text = "\n".join(parts)

                except Exception as exc:
                    result_text = f"Tool error: {exc}"

                tool_calls.append({
                    "tool": name,
                    "arguments": arguments,
                    "result": result_text,
                })

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text,
                }
            )

    return {
        "final_result": "Agent stopped after reaching the tool-call limit.",
        "tool_calls": tool_calls,
        "termination":"tool_call_limit",
    }