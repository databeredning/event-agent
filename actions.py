from mcp_client import call_tool


async def execute_decision(decision):
    action = decision.get("action")

    if action == "no_action":
        return {
            "status": "skipped",
            "action": "no_action",
        }

    if action == "turn_on_light":
        await call_tool(
            "ha_turn_on_test_light"
        )

        return {
            "status": "success",
            "action": "turn_on_light",
            "tool": "ha_turn_on_test_light",
        }

    return {
        "status": "rejected",
        "reason": f"Unknown action: {action}",
    }
