from mcp.server.mcpserver import MCPServer

from ha_client import get_state, turn_on_light


mcp = MCPServer("event-agent-homeassistant")

TEST_LIGHT = "light.sov4_tak"


@mcp.tool()
def ha_get_state(entity_id: str) -> dict:
    """
    Get the current state of a Home Assistant entity.

    Use this when the current state of a specific entity is needed.
    Returns only a small, bounded result.
    """
    state = get_state(entity_id)

    return {
        "entity_id": state["entity_id"],
        "state": state["state"],
    }


@mcp.tool()
def ha_turn_on_test_light() -> dict:
    """
    Turn on the event-agent test light.

    This tool can only control the configured test light.
    It cannot control arbitrary Home Assistant entities.
    """
    turn_on_light(TEST_LIGHT)

    return {
        "status": "success",
        "entity_id": TEST_LIGHT,
        "state": "on",
    }


if __name__ == "__main__":
    mcp.run()
