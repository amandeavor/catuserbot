# Aetheris V5 RC1 Architectural Baseline

**Date:** 2026-09-04  
**Git Branch:** `aetheris-v5`  
**HEAD Commit:** `8e10d249` (`fix(hardening): rigorous adversarial hardening, MTProto compliance, and verification`)  
**Parent Commit:** `8f579ae1` (`feat(v5): Aetheris V5 complete architectural migration and production upgrade`)  
**Target Release:** `5.0.0-rc1`  

---

## 1. System Inventory

### 1.1 Core Architecture & Modules
| Subsystem | Primary Implementation Path | Status / Current Evidence Level |
| :--- | :--- | :--- |
| **Transport Abstraction** | `userbot/core/transport/` (`interface.py`, `telethon_adapter.py`, `mock_adapter.py`) | **INTEGRATION TESTED** |
| **Plugin Lifecycle & Hot-Reload** | `userbot/core/plugins/` (`manifest.py`, `generation.py`, `registry.py`, `manager.py`, `compatibility.py`) | **INTEGRATION TESTED** (150 torture cycles) |
| **Job Supervisor & Concurrency** | `userbot/core/jobs/supervisor.py` | **UNIT & TORTURE TESTED** (1,000 concurrent jobs, pause/resume, cooperative cancellation) |
| **MTProto FloodShield** | `userbot/core/flood_shield.py` & `userbot/core/client.py` (`__call__` override) | **INTEGRATION TESTED** |
| **Command Parser** | `userbot/core/parser.py` & `userbot/helpers/utils/flags.py` | **UNIT & BENCHMARKED** (62.2k ops/s) |
| **File Transfer Engine** | `userbot/core/transfer/engine.py` | **UNIT TESTED** (Strict 512 KiB MTProto cap) |
| **Secure Callbacks** | `userbot/core/callbacks.py` | **UNIT TESTED** (15-byte opaque HMAC tokens, <=64 bytes) |
| **Web Dashboard** | `userbot/core/web/server.py` & `templates.py` | **INTEGRATION TESTED** (127.0.0.1 binding, constant-time token auth, 64 KB body cap) |
| **Database Storage Tier** | `userbot/sql_helper/__init__.py` & `globals.py` | **INTEGRATION TESTED** (Explicit SQLite/PostgreSQL modes; split-brain fallback removed) |
| **AI Fabric** | `userbot/core/ai/` (`interface.py`, `providers.py`, `router.py`, `memory.py`) | **IMPLEMENTED_AND_MOCK_TESTED** (REST contract schemas verified) |

### 1.2 Plugin & Command Parity
- **Total Discovered Plugins:** 138 modules in `userbot/plugins/`
- **Total Commands:** 396 commands discovered via AST inspection
- **Total Watchers:** 8 event watchers
- **Missing or Dropped Commands vs Master:** 0 (Parity ratio: 1.0)
- **Documented in:** `docs/V5_PLUGIN_COMPATIBILITY_AUDIT.md` and `artifacts/v4_v5_handler_diff.json`

### 1.3 Test Suite Status
- **Total Tests Passing:** 45 of 45 (`pytest -v tests/` in 26.41s)
- **Coverage Areas:** AI contracts, AI router, application startup, callbacks, flood shield, hot reload torture, jobs torture, parser, plugin lifecycle, storage cache, storage resilience, transfer engine.

---

## 2. Identified RC1 Weaknesses & Gaps Targeted for RC2

1. **Unmanaged Tasks in Legacy Plugins:**
   - `autoprofile.py` contains 7 top-level unmanaged infinite loops (`catub.loop.create_task(...)`) started at import time. These must be migrated to `JobSupervisor` so they don't leak or duplicate during reloads.
   - 6 other plugins use `create_task` for short-lived UI progress callbacks.
2. **Runtime Legacy Plugin Loading:**
   - Plugins were audited via AST compilation, but a live runtime loader harness must verify module imports and unloads under an active event loop.
3. **Telethon RPC Interception Boundary:**
   - Overriding `__call__` requires a comprehensive classification of internal Telethon protocol maintenance RPCs (e.g. `PingDelayDisconnectRequest`, `ResendQuery`, `MsgsAck`, `HttpWait`, `GetDifferenceRequest`) to guarantee protocol health.
4. **Parallel File Transfer Reassembly & Failure Injection:**
   - Validating chunk reassembly with mocked out-of-order latency, transfer cancellation at 10% and 50%, and bounded retry handling.
5. **Real Plugin Hot-Reloading:**
   - Testing real legacy plugins (stateless, DB-backed, and supervised task plugins) under simulated traffic.
6. **Production Soak Harness & Resource Leak Monitoring:**
   - Automated tracking of RSS, heap, task count, FDs, and event-loop lag.
7. **Version Promotion:**
   - Promote to `5.0.0-rc2` once all RC2 gates pass.
