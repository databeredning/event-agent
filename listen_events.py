import asyncio
import json
import os
from uuid import uuid4

import websockets
from dotenv import load_dotenv

from mcp_client import mcp_session
from reasoning import run_agent
from context import build_context
from triggers import process_state_change
from trace import (
    emit,
    trace_trigger,
    trace_context,
    trace_final_result,
    trace_error,
    trace_run_start,
    trace_run_end,
    trace_memory_retrieval,
)

from experience_store import init_db, save_experience, get_recent_experience
from memory import build_memory

load_dotenv()

HA_URL = os.environ["HA_URL"].rstrip("/")
HA_TOKEN = os.environ["HA_TOKEN"]

WS_URL = (
    HA_URL
    .replace("http://", "ws://")
    .replace("https://", "wss://")
    + "/api/websocket"
)


async def main():
    init_db()

    async with websockets.connect(WS_URL) as websocket:

        # Home Assistant asks us to authenticate.
        message = json.loads(await websocket.recv())
        emit("CONNECTION", message)

        # Authenticate.
        await websocket.send(json.dumps({
            "type": "auth",
            "access_token": HA_TOKEN,
        }))

        message = json.loads(await websocket.recv())
        emit("CONNECTION", message)

        # Subscribe to Home Assistant state changes.
        await websocket.send(json.dumps({
            "id": 1,
            "type": "subscribe_events",
            "event_type": "state_changed",
        }))

        message = json.loads(await websocket.recv())
        emit("SUBSCRIPTION", message)

        # Keep listening for events.
        while True:
            message = json.loads(await websocket.recv())

            if message.get("type") != "event":
                continue

            event = message["event"]
            data = event["data"]

            # Convert the raw Home Assistant state change
            # into a semantic trigger.
            trigger = process_state_change(data)

            if trigger is None:
                continue

            # Give this agent run a unique identity.
            run_id = str(uuid4())

            trace_run_start(run_id)
            trace_trigger(trigger)

            # Gather only the context relevant to this event.
            agent_input = build_context(trigger)
            agent_input["run_id"] = run_id

            trace_context(agent_input)

            previous_experience = get_recent_experience(
                trigger["type"]
            )

            memory = build_memory(previous_experience)
            agent_input["memory"] = memory

            trace_memory_retrieval(memory)

            # Run the agent.
            async with mcp_session() as session:
                result = await run_agent(
                    session,
                    agent_input,
                )

                # Observe the environment after the agent has finished.
                target_entity = (
                    agent_input["context"]["target_light"]["entity_id"]
                )

                outcome_result = await session.call_tool(
                    "ha_get_state",
                    arguments={
                        "entity_id": target_entity,
                    },
                )

                outcome_content = []

                for content in outcome_result.content:
                    text = getattr(content, "text", None)

                    if text is not None:
                        try:
                            value = json.loads(text)
                        except (json.JSONDecodeError, TypeError):
                            value = text

                        outcome_content.append(value)

                post_observation = (
                    outcome_content[0]
                    if outcome_content
                    else None
                )

                before_state = (
                    agent_input["context"]["target_light"]["state"]
                )

                after_state = (
                    post_observation.get("state")
                    if post_observation
                    else None
                )

                outcome = {
                    "before_state": before_state,
                    "after_state": after_state,
                    "changed": (
                        before_state != after_state
                        if after_state is not None
                        else None
                    ),
                }

            # Assemble a structured account of this run.
            experience = {
                "run_id": run_id,
                "trigger": trigger,
                "context": agent_input["context"],
                "tool_calls": result["tool_calls"],
                "post_observation": post_observation,
                "outcome": outcome,
                "execution": {
                    "termination": result["termination"],
                },            
                "final_result": result["final_result"],
            }

            trace_final_result(experience)

            save_experience(experience)

            trace_run_end(run_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except Exception as error:
        trace_error(error)
        raise
