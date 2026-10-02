def process_state_change(data):
    entity_id = data["entity_id"]

    old_state = data["old_state"]
    new_state = data["new_state"]

    if old_state is None or new_state is None:
        return None

    old_value = old_state["state"]
    new_value = new_state["state"]

    if (
        entity_id == "light.sov4_fonster"
        and old_value == "off"
        and new_value == "on"
    ):
        return {
            "type": "motion_detected",
            "area": "test",
            "source": entity_id,
        }

    return None
