import os

import requests
from dotenv import load_dotenv


load_dotenv()

HA_URL = os.environ["HA_URL"].rstrip("/")
HA_TOKEN = os.environ["HA_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}


def get_state(entity_id):
    response = requests.get(
        f"{HA_URL}/api/states/{entity_id}",
        headers=HEADERS,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def turn_on_light(entity_id):
    response = requests.post(
        f"{HA_URL}/api/services/light/turn_on",
        headers=HEADERS,
        json={
            "entity_id": entity_id,
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()
