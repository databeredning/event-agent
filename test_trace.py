"""Offline checks for observational tracing; no external services are started."""
import asyncio
import io
import json
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import trace
import reasoning
import mcp_client


class TraceTests(unittest.TestCase):
    def test_redaction_and_private_reasoning(self):
        payload = {
            "Authorization": "Bearer header-secret",
            "nested": [{"api_key": "key-secret"}],
            "content": json.dumps({"access_token": "embedded-secret"}),
            "message": "credential=inline-secret Bearer bearer-secret env-secret",
            "response": "<think>private-thought</think>visible",
            "reasoning_content": "hidden-field",
        }
        original = json.dumps(payload)
        output = io.StringIO()
        with patch.dict('os.environ', {"HA_TOKEN": "env-secret"}), redirect_stderr(output):
            trace.trace_context(payload)
        rendered = output.getvalue()
        for secret in ("header-secret", "key-secret", "embedded-secret", "inline-secret",
                       "bearer-secret", "env-secret", "private-thought", "hidden-field"):
            self.assertNotIn(secret, rendered)
        self.assertIn("CONTEXT", rendered)
        self.assertIn("visible", rendered)
        self.assertEqual(json.dumps(payload), original)

    def test_render_failure_is_contained(self):
        with patch.object(trace, 'render_terminal', side_effect=OSError('closed stream')):
            trace.trace_trigger({"type": "motion_detected"})

    def test_model_request_and_response_unchanged(self):
        content = '{"action": "no_action", "reason": "already on"}'
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=content, reasoning_content="must not appear"))])
        create = AsyncMock(return_value=completion)
        agent_input = {"context": {"state": "on"}}
        output = io.StringIO()
        with patch.object(reasoning.client.chat.completions, 'create', create), redirect_stderr(output):
            result = asyncio.run(reasoning.reason(agent_input))
        self.assertEqual(result, json.loads(content))
        create.assert_awaited_once_with(model=reasoning.LLM_MODEL, temperature=0, messages=[
            {"role": "system", "content": reasoning.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(agent_input)},
        ])
        self.assertIn('LLM REQUEST', output.getvalue())
        self.assertIn('LLM RESPONSE', output.getvalue())
        self.assertNotIn('must not appear', output.getvalue())

    def test_mcp_result_preserved_and_serialized(self):
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(content=[TextContent(type='text', text='{"status": "success"}')])
        session = AsyncMock()
        session.call_tool.return_value = result
        session_context = AsyncMock()
        session_context.__aenter__.return_value = session
        stdio_context = AsyncMock()
        stdio_context.__aenter__.return_value = ('read', 'write')
        output = io.StringIO()
        with patch.object(mcp_client, 'stdio_client', return_value=stdio_context), \
                patch.object(mcp_client, 'ClientSession', return_value=session_context), \
                redirect_stderr(output):
            actual = asyncio.run(mcp_client.call_tool('ha_turn_on_test_light'))
        self.assertIs(actual, result)
        session.call_tool.assert_awaited_once_with('ha_turn_on_test_light', arguments={})
        self.assertIn('TOOL CALL', output.getvalue())
        self.assertIn('MCP RESULT', output.getvalue())
        self.assertIn('success', output.getvalue())


if __name__ == '__main__':
    unittest.main()
