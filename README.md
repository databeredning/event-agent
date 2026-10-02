# Event Agent

A small event-driven AI agent for Home Assistant, built as a learning project to explore how an agent can run autonomously, react to real-world events, gather context, reason with a local LLM, and act through controlled MCP tools.

The project uses:

- **Home Assistant** as the event source and external environment
- **WebSockets** for real-time Home Assistant events
- **Qwen 3 8B** running locally through `llama-server`
- **MCP** for controlled tool access
- **Python** as the agent runtime
- **Structured tracing** to make the complete agent loop observable

The main goal is not sophisticated home automation. The deliberately simple motion/light example makes the architecture easy to understand and inspect.

## Architecture

The agent follows an event-driven sense → reason → act loop:

```text
                    Home Assistant
                          │
                    WebSocket event
                          │
                          ▼
                  listen_events.py
                          │
                          ▼
                     triggers.py
                          │
                    semantic event
                          │
                          ▼
                     context.py
                          │
                    relevant context
                          │
                          ▼
                       Qwen
                    ┌─────┴─────┐
                    │           │
               final answer   tool call
                                │
                                ▼
                               MCP
                                │
                                ▼
                            server.py
                                │
                                ▼
                          ha_client.py
                                │
                         Home Assistant
                                │
                                ▼
                         physical action
                                │
                                ▼
                           tool result
                                │
                                └──────► Qwen
```

The important distinction is that the LLM does not run continuously.

The **agent service** continuously listens for events. The LLM is invoked only when an event produces a meaningful trigger.

## Example

For development, a Home Assistant light is used to emulate a motion sensor:

```text
light.sov4_fonster
off → on
```

The trigger layer converts this Home Assistant-specific state transition into:

```json
{
  "type": "motion_detected",
  "area": "test",
  "source": "light.sov4_fonster"
}
```

The context builder then gathers relevant information:

```json
{
  "event": {
    "type": "motion_detected",
    "area": "test",
    "source": "light.sov4_fonster"
  },
  "context": {
    "time": "...",
    "target_light": {
      "entity_id": "light.sov4_tak",
      "state": "off"
    }
  }
}
```

Qwen receives this context together with the tools exposed by the MCP server.

For example:

```text
ha_get_state(entity_id)
ha_turn_on_test_light()
```

If Qwen determines that the light should be turned on, it generates an actual tool call:

```text
ha_turn_on_test_light()
```

The runtime executes that tool through MCP, the MCP server calls Home Assistant, and the result is returned to Qwen.

There is no hardcoded mapping such as:

```python
if model_decision == "turn_on_light":
    call_tool("ha_turn_on_test_light")
```

The model selects from the capabilities exposed by MCP.

## Components

### `listen_events.py`

The main event runtime.

It:

1. Connects to the Home Assistant WebSocket API.
2. Authenticates.
3. Subscribes to `state_changed` events.
4. Passes events through the trigger layer.
5. Builds context for relevant triggers.
6. Starts an MCP session.
7. Runs the LLM/tool loop.
8. Waits for the next event.

This process is intended to remain running as a service.

### `triggers.py`

Converts low-level external events into semantic agent events.

For example:

```text
Home Assistant:

light.sov4_fonster
off → on

        ↓

Agent:

motion_detected
```

This keeps Home Assistant implementation details out of the reasoning layer.

### `context.py`

Builds a small, relevant context for each triggered agent run.

Instead of dumping the entire Home Assistant state into the LLM context, it retrieves only information useful for the current decision.

For the current example this includes:

```text
event
time
target light
target light state
```

This keeps model context bounded and intentional.

### `reasoning.py`

Contains the LLM agent loop.

It:

1. Retrieves the available MCP tools.
2. Converts their schemas to OpenAI-compatible function definitions.
3. Sends the event, context, and tools to Qwen.
4. Detects model-generated tool calls.
5. Executes those calls through MCP.
6. Adds tool results back into the conversation.
7. Calls Qwen again.
8. Continues until Qwen returns a response without another tool call.

Conceptually:

```text
Qwen
  │
  │ tool call
  ▼
MCP
  │
  │ tool result
  ▼
Qwen
  │
  │ maybe another tool call
  ▼
...
  │
  ▼
final response
```

A tool-call limit prevents an agent run from looping indefinitely.

### `mcp_client.py`

Creates the MCP client session used by the agent runtime.

Communication with the local MCP server uses STDIO.

The MCP session stays alive for the duration of an agent run so the model can perform multiple tool calls if necessary.

### `server.py`

The Home Assistant MCP server.

It defines the capabilities available to the agent.

Current tools include operations such as:

```text
ha_get_state
ha_turn_on_test_light
```

The MCP server acts as a capability and safety boundary between the LLM and Home Assistant.

The model does **not** receive unrestricted Home Assistant API access.

For example, the current write tool is deliberately:

```text
ha_turn_on_test_light()
```

rather than a generic:

```text
call_home_assistant_service(
    domain,
    service,
    entity_id,
    data
)
```

This limits what the autonomous agent can change.

### `ha_client.py`

The low-level Home Assistant REST client.

It knows how to perform operations such as:

```text
GET /api/states/<entity>
POST /api/services/light/turn_on
```

Higher layers do not need to know the Home Assistant HTTP implementation details.

### `trace.py`

Provides structured observability for autonomous agent runs.

Instead of treating the agent as a black box, important boundaries are displayed in the terminal:

```text
CONNECTION
SUBSCRIPTION
TRIGGER
CONTEXT
LLM REQUEST
LLM RESPONSE
TOOL CALL
MCP RESULT
FINAL RESULT
ERROR
```

A run therefore looks similar to observing an AI chat with tool use:

```text
TRIGGER
    ↓
CONTEXT
    ↓
LLM REQUEST
    ↓
LLM RESPONSE
    ↓
TOOL CALL
    ↓
MCP RESULT
    ↓
LLM REQUEST
    ↓
LLM RESPONSE
    ↓
FINAL RESULT
```

The trace shows application-visible messages and tool activity. It does not attempt to expose private model chain-of-thought.

Raw Home Assistant events can optionally be enabled for debugging without flooding normal agent traces with unrelated sensor updates.

## Agent Loop

A complete autonomous run currently looks like this:

```text
1. Home Assistant state changes

2. WebSocket listener receives the event

3. Trigger layer determines whether it is interesting

4. A semantic event is produced

       motion_detected

5. Context is gathered

       target_light = off

6. MCP tools are discovered

       ha_get_state
       ha_turn_on_test_light

7. Qwen receives:

       system instructions
       event
       context
       available tools

8. Qwen selects:

       ha_turn_on_test_light()

9. Runtime executes the tool through MCP

10. MCP server calls Home Assistant

11. Home Assistant turns the light on

12. MCP returns:

       status = success
       state = on

13. Tool result is added to the LLM conversation

14. Qwen receives the updated conversation

15. Qwen returns a final response

16. Agent waits for the next event
```

## Setup

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file containing the Home Assistant connection details:

```env
HA_URL=http://home-assistant-host:8123
HA_TOKEN=your-long-lived-access-token
```

Do not commit `.env`.

The local LLM is expected to be available through an OpenAI-compatible `llama-server` endpoint:

```text
http://127.0.0.1:8080/v1
```

The current model name is:

```text
qwen3-8b
```

## Running

Activate the environment:

```bash
source .venv/bin/activate
```

Start the event agent:

```bash
python listen_events.py
```

The process connects to Home Assistant and waits for relevant events.

For the current development scenario:

```text
light.sov4_fonster
```

is used to emulate motion.

Changing it:

```text
off → on
```

produces a `motion_detected` trigger.

The agent then evaluates the current state of:

```text
light.sov4_tak
```

and may choose to call the MCP tool that turns it on.

## MCP Development

The MCP server can be tested independently:

```bash
mcp dev server.py
```

This allows the Home Assistant tools to be inspected and invoked without involving the LLM or event runtime.

This separation is useful when debugging:

```text
MCP Inspector
      ↓
server.py
      ↓
ha_client.py
      ↓
Home Assistant
```

before testing the complete system:

```text
Home Assistant event
      ↓
agent
      ↓
Qwen
      ↓
MCP
      ↓
Home Assistant action
```

## Design Principles

### Events wake the agent

The LLM does not continuously poll Home Assistant.

Home Assistant events determine when reasoning is necessary.

### Triggers add meaning

Raw infrastructure events are converted into semantic events before reaching the reasoning layer.

```text
state_changed + off → on
```

becomes:

```text
motion_detected
```

### Context is selective

External systems may contain enormous amounts of state.

Only information relevant to the current event should be added to the model context.

### The LLM decides, the runtime orchestrates

Qwen chooses whether and how to use the capabilities presented to it.

Python manages the conversation, executes requested tools, returns results, and enforces iteration limits.

### MCP defines capabilities

The MCP server determines what the agent is capable of doing.

The model cannot call Home Assistant operations that have not been exposed as tools.

### Prefer narrow tools

Autonomous write capabilities should be intentionally constrained.

Prefer:

```text
ha_turn_on_test_light()
```

over:

```text
execute_arbitrary_home_assistant_service(...)
```

especially while developing and testing autonomous behavior.

### Observability is part of the architecture

An autonomous system should make it possible to understand:

```text
what happened
→ what the agent knew
→ what was sent to the model
→ what the model requested
→ what tools executed
→ what the tools returned
→ how the agent finished
```

Tracing is therefore treated as a first-class component rather than a collection of temporary `print()` statements.

## What This Project Demonstrates

The project started as a simple question:

> How can an AI agent run on its own and react to things happening in the real world?

The resulting architecture demonstrates that autonomy does not mean continuously running an LLM.

Instead:

```text
environment
    ↓
event
    ↓
trigger
    ↓
context
    ↓
reasoning
    ↓
tool selection
    ↓
action
    ↓
environment changes
```

The long-running component is the **event-driven agent runtime**.

The LLM is a reasoning component invoked when necessary.

The result is a small but complete autonomous agent capable of:

- sensing external events
- deciding when an event matters
- gathering relevant state
- reasoning with a local LLM
- discovering available capabilities
- selecting MCP tools
- affecting a real external system
- observing tool results
- continuing reasoning after an action
- exposing the complete execution flow through structured tracing

## Next Steps

This project currently focuses on **autonomy**, not learning.

A natural next phase is to explore:

```text
state
memory
history
outcomes
feedback
learning
```

That introduces a different question:

> How can an autonomous agent use previous events and outcomes to influence future decisions?

That should be treated as a separate architectural layer rather than simply adding more information to the prompt.