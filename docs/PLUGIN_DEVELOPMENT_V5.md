# Plugin Development Guide: Aetheris V5

Aetheris V5 introduces a modular, versioned plugin system with state persistence, structured concurrency, and distributed observability. This guide outlines how to build next-generation V5 plugins.

---

## 1. V5 Plugin Structure

A modern V5 plugin can be written as a single Python module or a package inside `userbot/plugins/`. It specifies a `PluginManifest`, implements optional lifecycle hooks, and defines command handlers.

```python
# userbot/plugins/v5_system_monitor.py

import asyncio
from typing import Any, Dict
from userbot.core.plugins.manifest import PluginManifest
from userbot.core.jobs.supervisor import CancellationToken, JobPriority, supervisor
from userbot.core.observability.tracer import tracer
from userbot.core.parser import command_parser
from userbot.utils import catcmd

# 1. Plugin Manifest
__plugin_manifest__ = PluginManifest(
    name="system_monitor",
    version="1.0.0",
    author="Aetheris Intelligence",
    description="Real-time system telemetry and auto-alerts",
    dependencies=[],
    capabilities=["system_metrics", "background_worker"],
    min_core_version="5.0.0",
)

# 2. State Storage
_plugin_state: Dict[str, Any] = {
    "poll_interval": 30,
    "total_alerts": 0,
}

# 3. Lifecycle Hooks
async def on_plugin_load():
    """Triggered when generation is activated."""
    supervisor.submit_job(
        name="system_monitor_worker",
        coro_func=_monitor_loop,
        priority=JobPriority.BACKGROUND,
    )

async def on_plugin_unload():
    """Triggered when generation is unloaded or during shutdown."""
    pass

async def on_plugin_pre_reload():
    """Pre-reload preparation before state export."""
    pass

def export_plugin_state() -> Dict[str, Any]:
    """Serializes mutable runtime state across hot-reloads."""
    return _plugin_state.copy()

def import_plugin_state(state: Dict[str, Any]):
    """Restores serialized runtime state in the new generation."""
    global _plugin_state
    _plugin_state.update(state)

# 4. Background Worker with Structured Concurrency
async def _monitor_loop(token: CancellationToken):
    while not token.is_cancelled:
        # Perform background monitoring
        await token.sleep(_plugin_state["poll_interval"])

# 5. Command Handlers
@catcmd(pattern="sysmon(?:\\s+(.*))?$")
async def sysmon_handler(event):
    with tracer.start_span("sysmon_command"):
        raw_text = event.raw_text
        cmd = command_parser.parse(raw_text)

        # Access POSIX flags
        verbose = cmd.has_flag("v") or cmd.has_flag("verbose")
        interval = cmd.get_flag("interval", type_cast=int)

        if interval:
            _plugin_state["poll_interval"] = interval
            await event.edit(f"**[+] Monitoring interval updated to {interval}s**")
            return

        response = (
            f"**[ AETHERIS V5 SYSTEM MONITOR ]**\n"
            f"- **Poll Interval**: `{_plugin_state['poll_interval']}s`\n"
            f"- **Total Alerts**: `{_plugin_state['total_alerts']}`\n"
            f"- **Verbose Mode**: `{'Enabled' if verbose else 'Disabled'}`"
        )
        await event.edit(response)
```

---

## 2. Best Practices for V5 Plugins

### 2.1 Always Use Cooperative Cancellation
Never use uncontrolled `while True:` loops. Always accept a `CancellationToken` in background workers and use `await token.sleep(seconds)`:
```python
async def my_worker(token: CancellationToken):
    while not token.is_cancelled:
        # Work logic here
        await token.sleep(10)
```

### 2.2 Use `CommandParserV5` for Arguments
Avoid splitting `event.text` manually with `.split(" ")`. Use `command_parser.parse(event.raw_text)`:
- Supports quotes: `.cmd "my quoted value" --tag=production`
- Supports short flags: `.cmd -rfv`
- Supports type conversion: `cmd.get_flag("count", default=1, type_cast=int)`

### 2.3 Utilize the Multi-Provider AI Fabric
When building AI-powered commands, import the router directly:
```python
from userbot.core.ai import ai_router

response = await ai_router.complete(
    prompt="Explain quantum entanglement",
    system_prompt="You are a concise physics tutor.",
    provider="gemini", # Automatically falls back if provider fails
)
```

### 2.4 Secure Callbacks with HMAC Tokens
When sending inline keyboards with action callbacks, generate an opaque token:
```python
from userbot.core.callbacks import callback_manager

token = callback_manager.generate_token(
    user_id=event.sender_id,
    action="confirm_purge",
    payload={"chat_id": event.chat_id, "count": 50},
    ttl_seconds=120,
)
# Button callback data will be: "purge:abf128c94..."
```
