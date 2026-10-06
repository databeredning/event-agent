"""Observational trace events, with a replaceable terminal renderer.

Only application boundary data belongs here; never pass model reasoning fields.
Rendering and redaction failures are contained so tracing cannot stop the agent.
"""

import json
import os
import re
import sys
from datetime import datetime


_REDACTED = "[REDACTED]"
_SENSITIVE = re.compile(
    r"token|secret|password|passwd|api[_-]?key|authorization|credential|cookie",
    re.IGNORECASE,
)
_PRIVATE = {"reasoning", "reasoning_content", "chain_of_thought"}

def trace_memory_retrieval(memory):
    emit("MEMORY RETRIEVAL", memory)

def trace_run_start(run_id):
    emit("RUN START", {
        "run_id": run_id,
    })

def trace_run_end(run_id):
    emit("RUN END", {
        "run_id": run_id,
    })

def _clean(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): _REDACTED if _SENSITIVE.search(str(key))
            or str(key).lower() in _PRIVATE else _clean(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, str):
        # JSON embedded in prompts or MCP TextContent needs the same redaction.
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            decoded = None
        if isinstance(decoded, (dict, list)):
            return _clean(decoded)
        value = re.sub(r"<think\b[^>]*>.*?(?:</think>|$)",
                       "[PRIVATE REASONING OMITTED]", value,
                       flags=re.IGNORECASE | re.DOTALL)
        for key, secret in os.environ.items():
            if _SENSITIVE.search(key) and secret:
                value = value.replace(secret, _REDACTED)
        value = re.sub(r"\bBearer\s+[^\s\"']+", "Bearer " + _REDACTED,
                       value, flags=re.IGNORECASE)
        value = re.sub(
            r"\b(token|secret|password|passwd|api[_-]?key|authorization|credential)"
            r"(\s*[:=]\s*)([^\s,;]+)",
            r"\1\2" + _REDACTED, value, flags=re.IGNORECASE,
        )
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _clean(str(value))


def render_terminal(event):
    """Replace this sink later to send the same event to JSONL or a UI."""
    body = event["data"]
    if event["stage"] == "LLM REQUEST" and isinstance(body, dict):
        parts = [json.dumps({key: value for key, value in body.items()
                             if key != "messages"}, ensure_ascii=False, indent=2)]
        for message in body.get("messages", []):
            content = message.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            parts.append(f"{message.get('role', 'message').title()}:\n{content}")
        body = "\n\n".join(parts)
    elif not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False, indent=2)
    separator = "━" * 40
    print(f"\n{separator}\n{event['stage']}  {event['timestamp']}\n"
          f"{separator}\n{body}", file=sys.stderr, flush=True)


def emit(stage, data):
    try:
        render_terminal({
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "stage": stage,
            "data": _clean(data),
        })
    except Exception:
        # A broken output stream or unexpected payload must not affect execution.
        pass


def trace_event(data):
    """Raw listener events are opt-in; read after the app loads its .env."""
    if os.environ.get("TRACE_RAW_EVENTS", "false").strip().lower() == "true":
        emit("EVENT", data)


def trace_trigger(trigger):
    emit("TRIGGER", trigger)


def trace_context(context):
    emit("CONTEXT", context)


def trace_llm_request(request):
    emit("LLM REQUEST", request)


def trace_llm_response(content):
    emit("LLM RESPONSE", content)


def trace_tool_call(name, arguments):
    emit("TOOL CALL", {"name": name, "arguments": arguments})


def trace_tool_result(result):
    emit("MCP RESULT", result)


def trace_final_result(result):
    emit("FINAL RESULT", result)


def trace_error(error):
    emit("ERROR", {"type": type(error).__name__, "message": str(error)})
