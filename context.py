from datetime import datetime

from ha_client import get_state


TARGET_LIGHT = "light.sov4_tak"


def build_context(trigger):
    now = datetime.now().astimezone()

    target_light = get_state(TARGET_LIGHT)

    return {
        "event": trigger,
        "context": {
            "time": now.isoformat(timespec="seconds"),
            "target_light": {
                "entity_id": target_light["entity_id"],
                "state": target_light["state"],
            },
        },
    }
