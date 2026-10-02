import json

from openai import AsyncOpenAI

from trace import trace_llm_request, trace_llm_response


LLM_BASE_URL = "http://127.0.0.1:8080/v1"
LLM_MODEL = "qwen3-8b"

client = AsyncOpenAI(
    base_url=LLM_BASE_URL,
    api_key="not-needed",
)


SYSTEM_PROMPT = """
You are the reasoning component of an event-driven home automation agent.

You receive an event and a small amount of relevant context.

For now, you may make only one of these decisions:

- turn_on_light
- no_action

Rules:
- If motion is detected and the target light is off, choose turn_on_light.
- If the target light is already on, choose no_action.
- Do not invent information that is not present in the input.

Return only valid JSON in this format:

{
  "action": "turn_on_light",
  "reason": "brief explanation"
}
"""


async def reason(agent_input):
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
    request = {"model": LLM_MODEL, "messages": messages, "temperature": 0}
    trace_llm_request(request)
    response = await client.chat.completions.create(**request)

    content = response.choices[0].message.content

    trace_llm_response(content)

    return json.loads(content)
