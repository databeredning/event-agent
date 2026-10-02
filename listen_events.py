import asyncio
import json
import os

import websockets
from dotenv import load_dotenv

from actions import execute_decision
from context import build_context
from reasoning import reason
from triggers import process_state_change


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
        print("Received:", message)

        # Authenticate.
        await websocket.send(json.dumps({
            "type": "auth",
            "access_token": HA_TOKEN,
        }))

        message = json.loads(await websocket.recv())
        print("Received:", message)

        # Subscribe to Home Assistant state changes.
        await websocket.send(json.dumps({
            "id": 1,
            "type": "subscribe_events",
            "event_type": "state_changed",
        }))

        message = json.loads(await websocket.recv())
        print("Subscription:", message)

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

            print("TRIGGER:", trigger)

            # Gather only the context relevant to this event.
            agent_input = build_context(trigger)

            print("AGENT INPUT:", agent_input)

            # Ask Qwen what should happen.
            decision = await reason(agent_input)

            print("DECISION:", decision)

            # Execute the decision through our controlled
            # action boundary.
            result = await execute_decision(decision)

            print("ACTION RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())
