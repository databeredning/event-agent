import asyncio
import json
import os

import websockets
from dotenv import load_dotenv

from actions import execute_decision
from context import build_context
from reasoning import reason
from triggers import process_state_change
from trace import (emit, trace_event, trace_trigger, trace_context,
                   trace_final_result, trace_error)


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

            trace_event(data)

            # Convert the raw Home Assistant state change
            # into a semantic trigger.
            trigger = process_state_change(data)

            if trigger is None:
                continue

            trace_trigger(trigger)

            # Gather only the context relevant to this event.
            agent_input = build_context(trigger)

            trace_context(agent_input)

            # Ask Qwen what should happen.
            decision = await reason(agent_input)

            # Execute the decision through our controlled
            # action boundary.
            result = await execute_decision(decision)

            trace_final_result(result)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        trace_error(error)
        raise
