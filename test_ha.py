import os
import requests

from dotenv import load_dotenv


load_dotenv()

HA_URL = os.environ["HA_URL"].rstrip("/")
HA_TOKEN = os.environ["HA_TOKEN"]

headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}

entity_id = "binary_sensor.sheep_1_motion"

response = requests.get(
    f"{HA_URL}/api/states/{entity_id}",
    headers=headers,
    timeout=10,
)

response.raise_for_status()

state = response.json()

print("Entity:", state["entity_id"])
print("State:", state["state"])
print("Attributes:", state["attributes"])

