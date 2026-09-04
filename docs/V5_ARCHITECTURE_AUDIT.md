# AETHERIS V5: ARCHITECTURAL BASELINE & AUDIT REPORT

**Document ID:** `V5-AUDIT-001`  
**Date:** September 2026  
**Auditor:** Principal Systems Engineer & Telegram MTProto Specialist  
**Repository:** `amandeavor/catuserbot`  
**Baseline Version:** `Aetheris v4.0.0` (evolved from `TgCatUB/catuserbot v3.3.0`)  
**Target Version:** `Aetheris v5.0.0`  

---

## 1. EXECUTIVE SUMMARY

An exhaustive architectural audit of the active codebase was conducted prior to executing the V5 migration. The repository represents a heavily customized userbot with **139 active plugins**, an inline assistant bot, and legacy SQL database helpers. 

While the system is currently deployed and functional on Telethon, it exhibits significant architectural debt:
1. **Pervasive Framework Coupling**: Direct Telethon imports and types are tightly coupled throughout all 139 plugins and helpers.
2. **Event Loop Starvation**: Over 90 instances of synchronous, blocking `requests.get()` and `subprocess.check_output()` calls run directly inside async coroutine handlers.
3. **Ghost Callbacks & Brittle Unloading**: Dynamic plugin unloading relies on inspecting private Telethon attributes (`catub._event_builders`), which leaks event handlers and memory across successive reloads.
4. **Synchronous Database Roundtrips**: Database access (`userbot/sql_helper/globals.py`) executes synchronous SQLAlchemy queries with fresh connection churn on every incoming message without an in-memory cache layer.
5. **Absence of Unified Subprocess & Media Services**: Shell strings are formatted and executed via `asyncio.create_subprocess_shell` in several media plugins without argument array validation.
6. **Zero Automated Test Coverage**: The baseline repository contains zero unit or integration tests.

---

## 2. REPOSITORY ARCHITECTURE MAP

The execution and data flow from Telegram MTProto network to storage in Aetheris v4 is mapped below:

```
[Telegram Servers]
       │ (MTProto binary frames / TCP Abridged)
       ▼
[Telethon Client Session: userbot/core/session.py]
  - CatUserBotClient (session = StringSession)
  - Bot Assistant Client (session = "CatTgbot")
       │
       ▼
[Event Dispatcher: userbot/core/client.py & events.py]
  - Custom events.NewMessage and events.MessageEdited
  - Regex pattern compilation (REGEX_.regex1, REGEX_.regex2)
  - Raw event wrapper (cat_cmd / aetheris_cmd)
       │
       ▼
[Command Parser: userbot/helpers/utils/flags.py]
  - Primitive command splitting / basic shlex tokenization
  - Sudo permission lookup (synchronous gvarstatus query)
       │
       ▼
[Plugin Registry: userbot/core/__init__.py]
  - Global dictionaries: CMD_INFO, PLG_INFO, GRP_INFO, LOADED_CMDS
  - Module loader: userbot/utils/pluginmanager.py
       │
       ▼
[Plugin Handlers: userbot/plugins/*.py (139 files)]
  - Command execution, media parsing, formatting
       │
       ▼
[Storage & External Services]
  - Synchronous SQLAlchemy (userbot/sql_helper)
  - Unmanaged requests.get / subprocess calls
       │
       ▼
[Response to Telegram API]
  - edit_or_reply / send_message
```

---

## 3. COMPONENT AUDIT & WEAKNESS INVENTORY

### 3.1 Entrypoints & Lifecycle
* **`userbot/__main__.py`**: 
  - Starts background HTTP health daemon on `$PORT` via `threading.Thread(target=start_health_server, daemon=True)`.
  - Blocks on `catub.loop.run_until_complete(setup_bot())`.
  - Sequentially loads all 139 plugins in `load_plugins("plugins")` and assistant plugins in `load_plugins("assistant")`.
  - Starts external repo plugins synchronously.
* **`userbot/core/session.py`**:
  - Global singleton instantiations `catub` and `catub.tgbot` occur at module import time.
  - Calling `from userbot.core.session import catub` immediately triggers `catub.tgbot.start(bot_token=Config.TG_BOT_TOKEN)`, attempting network calls before the test environment can mock them.

### 3.2 Framework Coupling
* **Direct Telethon Dependence**:
  - Every single plugin directly calls `event.client`, `event.respond`, `event.edit`, or uses Telethon types (`MessageMediaWebPage`, `InputDocumentFileLocation`, `Button.inline`).
  - Decoupling requires a dual-mode transport adapter layer that allows new plugins to interact via high-level service protocols while preserving backward compatibility for existing Telethon event objects.

### 3.3 Global Mutable State
* The application state is maintained via unprotected global dictionaries:
  - `userbot.core.CMD_INFO`: Dictionary mapping command string to metadata list.
  - `userbot.core.PLG_INFO`: Dictionary mapping plugin stem name to command lists.
  - `userbot.core.GRP_INFO`: Categorized plugin registry.
  - `userbot.core.LOADED_CMDS`: Maps command string to wrapper coroutine functions.
  - `userbot.COUNT_MSG`, `userbot.USERS`, `userbot.LASTMSG`: Unbounded message counting dictionaries that grow indefinitely in memory over long uptimes.

### 3.4 Plugin Lifecycle & Hot-Reload Weaknesses
* **Inspection of `userbot/utils/pluginmanager.py`**:
  - `load_module()` imports via `importlib.util.spec_from_file_location()`, monkey-patches 15 globals (`mod.bot`, `mod.LOGS`, `mod.Config`, etc.) onto the module namespace, executes the module, and stores it in `sys.modules`.
  - `remove_plugin()` attempts to clean up event handlers by walking backwards over `catub._event_builders` and comparing `cb.__module__ == name`.
  - **Identified Failure Mode**: If a plugin registers anonymous functions, nested closures, or helper callbacks in other modules, `cb.__module__` does not match, leaving zombie/ghost callbacks active. Successive reloads cause duplicate message replies and memory leaks.

### 3.5 Event Loop Starvation & Blocking I/O
* **Synchronous HTTP Requests**:
  - 90+ occurrences of `requests.get()` across plugins (e.g. `alive.py`, `jikan.py`, `nekos.py`, `climate.py`, `musictool.py`).
  - When external endpoints experience high latency or timeouts (up to 10 seconds), the **entire asyncio loop is blocked**. All MTProto heartbeats, ping updates, and message handling stop.
* **Synchronous Shell Subprocesses**:
  - `userbot/plugins/channel_download.py`: Line 54: `ps = subprocess.Popen(("ls", tempdir), stdout=subprocess.PIPE)` and `output = subprocess.check_output(("wc", "-l"), stdin=ps.stdout)`.
  - These Unix-specific calls block the event loop and crash immediately on Windows environments.

### 3.6 Database Layer Coupling
* **`userbot/sql_helper/__init__.py` & `globals.py`**:
  - Implements a synchronous SQLAlchemy `scoped_session`.
  - Every `gvarstatus(key)` call issues a synchronous SQL query against PostgreSQL.
  - High-frequency event checks (e.g. checking whether sudo is enabled on every incoming message) repeatedly query the database synchronously without an in-memory LRU or TTL cache.
  - If `Config.DB_URI` is unset, `start()` throws an uncaught `AttributeError`, leaving `SESSION` undefined and causing cascading crashes on plugins attempting database operations.

### 3.7 Subprocess Security & Command Injection Hazards
* **`userbot/plugins/ffmpeg.py`**:
  - Lines 56 and 115 use `asyncio.create_subprocess_shell()` with formatted string interpolation instead of array-based argument vectors (`create_subprocess_exec`).
  - Malicious input inside media names or ffmpeg flags could result in shell command injection.

### 3.8 Secret Storage
* Sensitive keys (AI tokens, API keys, string sessions) are passed in environment variables and optionally stored in plaintext in the database `globals` table (`variable` and `value` columns).
* No encryption-at-rest layer exists for persistent tokens.

### 3.9 Long-Running Operations & Job Supervision
* Until V4's preliminary task manager was introduced, commands like `.download`, `.ytdl`, `.broadcast`, and `.purge` ran via fire-and-forget coroutines.
* There was no supervisor capable of tracking job phases, CPU/memory limits, cancellation tokens, or recovering state after dyno reboots.

---

## 4. TARGET ARCHITECTURE: AETHERIS V5

To address these vulnerabilities without breaking the 139 existing plugins, Aetheris V5 implements an incremental, layered architecture:

```text
┌────────────────────────────────────────────────────────┐
│                   TELEGRAM NETWORK                     │
└──────────────────────────┬─────────────────────────────┘
                           │ MTProto Updates / RPC
┌──────────────────────────▼─────────────────────────────┐
│                 TRANSPORT ADAPTER LAYER                │
│   • ITelegramTransport (Protocol)                      │
│   • TelethonTransportAdapter (Production V5)           │
│   • MockTransportAdapter (Automated Tests)             │
│   • Native/Hydrogram Abstract Hooks (Future Ready)     │
└──────────────────────────┬─────────────────────────────┘
                           │ Normalized Updates
┌──────────────────────────▼─────────────────────────────┐
│                 RPC & FLOOD SHIELD V5                  │
│   • Authoritative FLOOD_WAIT_X Enforcer + Positive Jitter│
│   • Priority Lanes (P0 System -> P5 Background Jobs)   │
│   • Per-Peer / Per-Method Adaptive Token Buckets       │
│   • Circuit Breaker (Closed / Half-Open / Open)        │
└──────────────────────────┬─────────────────────────────┘
                           │ Safe RPC Execution
┌──────────────────────────▼─────────────────────────────┐
│             CORE EVENT & DISPATCH SUBSYSTEM            │
│   • Unified Lexical Command Parser (GNU/POSIX flags)   │
│   • Blast Guard (Dry-run confirmations for bulk ops)   │
│   • Execution Tracer (event_id, rpc_id, latency log)   │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│          TRANSACTIONAL VERSIONED PLUGIN HOST           │
│   • Generation Scoping (plugin@gen_N)                  │
│   • Shadow Registry & Atomic Handler Swap              │
│   • Deterministic Lifecycle (on_load, on_quiesce)     │
│   • Legacy Telethon Compatibility Adapter              │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│                 SUPERVISED SERVICES FABRIC             │
│  ┌──────────────────┐ ┌──────────────────┐ ┌─────────┐ │
│  │ JobSupervisor V5 │ │ FileTransfer Eng │ │ MediaSvc│ │
│  │ (Priority Queues)│ │ (Adaptive Chunks)│ │ (FFmpeg)│ │
│  └──────────────────┘ └──────────────────┘ └─────────┘ │
│  ┌──────────────────┐ ┌──────────────────┐ ┌─────────┐ │
│  │ AI Service Router│ │ Storage & Vault  │ │ Telemetry│
│  │ (Multi-Provider) │ │ (Cache+Postgres) │ │ (HUD/Log)│
│  └──────────────────┘ └──────────────────┘ └─────────┘ │
└────────────────────────────────────────────────────────┘
```

---

## 5. MIGRATION ROADMAP & MITIGATION STRATEGY

| Defect / Debt Identified | V5 Architectural Solution | Risk Level |
| :--- | :--- | :--- |
| Framework coupling to Telethon | Introduce `ITelegramClient` protocol with Telethon adapter + backward compatibility layer | Low (Zero plugin breakage) |
| Ghost callbacks during reload | Implement versioned plugin generations (`plugin@N`) with shadow registries and atomic swaps | Medium (Requires atomic unbinding) |
| Event loop starvation (90+ `requests.get`) | Replace with asynchronous `httpx`/`aiohttp` clients & thread executor offloading | Low (Gradual migration) |
| Shell injection in `ffmpeg.py` | Centralize all FFmpeg invocations into a dedicated, validated `MediaService` using `create_subprocess_exec` | Low (Security enhancement) |
| Sync SQL queries on every message | Add thread-safe, in-memory LRU cache over `globals` table + SQLite automatic test fallback | Low (Zero config changes) |
| Uncontrolled long-running operations | Centralize into `JobSupervisor` with state machines (`QUEUED` -> `RUNNING` -> `COMPLETED`) | Low (Explicit tracking) |
| FloodWait crashes | Centralized Flood Shield intercepts Telegram RPC errors and enforces authoritative backoff | Low (Prevents bans) |

*Audit complete. Proceeding to Phase B: Foundation & Core Service Container.*
