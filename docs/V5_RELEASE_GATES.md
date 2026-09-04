# Aetheris V5 Release Gates and Verification Specification

This document defines the authoritative quality gates, verification criteria, and sign-off conditions for promoting **Aetheris V5** from Release Candidate (`5.0.0-rc1` / `5.0.0-rc2`) to **Production Stable (`5.0.0`)**.

---

## 1. Quality Gates Overview

| Gate | Domain | Objective | Threshold | Verification Method | Status |
|---|---|---|---|---|---|
| **GATE-1** | Syntax & Compilation | Ensure zero syntax/compilation errors | 100% clean | `python -m py_compile` | **PASSED** |
| **GATE-2** | Repository Hygiene | Zero tracked credentials, `.session`, `.db` | 0 violations | Secret & path scanning | **PASSED** |
| **GATE-3** | MTProto Maintenance | Bypass flood shield for heartbeats & maintenance | 12 RPC types verified | `tests/test_flood_shield.py` | **PASSED** |
| **GATE-4** | Task Migration | Eliminate raw `loop.create_task` in plugins | 100% supervised | `docs/V5_TASK_OWNERSHIP_AUDIT.md` | **PASSED** |
| **GATE-5** | Transfer Limits | Enforce MTProto 512 KiB part limits & backoff | <= 512 KiB chunks | `tests/test_transfer_integration.py` | **PASSED** |
| **GATE-6** | Unit & Integration | Full test suite execution | 100% pass rate | `pytest -v tests/` | **PASSED** |
| **GATE-7** | Plugin Dynamic Import | Dynamic load & unbind of all 138 plugins | 138/138 (100.0%) | `scripts/runtime_plugin_validator.py` | **PASSED** |
| **GATE-8** | Soak Stability | Bounded memory and loop lag under sustained load | Delta < 25MB, Lag < 15ms | `scripts/soak_test.py` | **PASSED** |
| **GATE-9** | Version Tagging | Synchronized versioning across core & web | `5.0.0-rc2` / `5.0.0` | `scripts/release_gate.py` | **PASSED** |

---

## 2. Gate Details and Implementation

### Gate 1: Syntax & Compilation Preflight
Every Python file across `userbot/`, `tests/`, and `scripts/` is compiled via `py_compile` under Python 3.13. Any `SyntaxError`, invalid escape sequence breaking compilation, or malformed AST triggers immediate failure.

### Gate 2: Repository Hygiene & Security
The repository is scanned for forbidden sensitive and stateful files:
- Telegram session files: `*.session`, `*.session-journal`
- Embedded databases: `*.db`, `*.sqlite`, `*.sqlite3`
- Environment secrets: `.env`, `.env.backup`
- Hardcoded API credentials in code: `api_id`, `api_hash`, `bot_token`.

### Gate 3: MTProto Maintenance RPC Classification
Telethon maintenance RPCs (`PingRequest`, `PingDelayDisconnectRequest`, `GetStateRequest`, `InitConnectionRequest`, `InvokeWithLayerRequest`, `DestroySessionRequest`, `GetDifferenceRequest`, `GetConfigRequest`, `GetNearestDcRequest`, `GetFutureSaltsRequest`, `MsgsAck`, `HttpWait`) are classified via `is_maintenance_request()` and routed through `RPCLane.P0_SYSTEM`. They bypass token buckets, circuit breakers, and rate limit delays to maintain uninterrupted connection heartbeats.

### Gate 4: Unmanaged Legacy Task Governance
All legacy background tasks (including all 7 autonomous background loops in `userbot/plugins/autoprofile.py`: `autoname`, `autobio`, `autopfp`, `autopic`, `digitalpfp`, `bloom`, `custompfp`) have been converted from raw `loop.create_task()` calls to supervised workers under `JobSupervisor` using cooperative `CancellationToken.sleep()`. Plugin reload triggers `job_supervisor.cancel_plugin_jobs(plugin_name)` to eliminate orphaned worker tasks.

### Gate 5: Transfer Engine Authoritative MTProto Limits
Telegram MTProto specifications dictate that `upload.saveFilePart` and `upload.saveBigFilePart` chunk sizes must divide evenly by 1024 bytes and must **never** exceed 512 KiB (524,288 bytes). Any chunk > 512 KiB results in Telegram error `400: FILE_PART_TOO_BIG`. The transfer engine strictly clamps all chunk plans to 512 KiB maximum, supports out-of-order parallel reassembly, and enforces exponential backoff retry.

### Gate 6: Automated Test Suite Execution
The entire test suite in `tests/` executes with 100% pass rate:
- `test_autoprofile_supervisor.py` (Cooperative cancellation, lifecycle hooks)
- `test_flood_shield.py` (Circuit breakers, flood wait positive jitter, maintenance RPCs)
- `test_jobs_torture.py` (Worker concurrency, crash recovery, timeout enforcement)
- `test_plugin_lifecycle.py` (Generation isolation, state export/import, atomic swap)
- `test_real_plugin_reload.py` (Real plugin reload of alive, custom, autoprofile)
- `test_transfer_engine.py` (Chunk sizing, 512 KiB cap, coverage)
- `test_transfer_integration.py` (Shuffled reassembly, 10% & 50% cooperative cancellation, retry backoff)

### Gate 7: Runtime Dynamic Plugin Validation
`scripts/runtime_plugin_validator.py` executes against all 138 plugins in an offline sandbox. Every plugin is dynamically loaded via `load_module()`, its command bindings inspected in `atomic_registry`, and then cleanly unbound via `remove_plugin()`, `atomic_registry.unregister_plugin()`, and `job_supervisor.cancel_plugin_jobs()`. The requirement is 138/138 (100.0%) passed with 0 dangling handlers and 0 dangling jobs.

### Gate 8: Long-Running Stability & Soak Testing
`scripts/soak_test.py` generates sustained concurrent traffic across the job supervisor, transfer engine, and flood shield. Real-time telemetry recorded in `artifacts/soak_metrics.jsonl` tracks:
- RSS Memory Delta (Net change must be < 25 MB)
- Heap Objects Count (No unbounded allocation leaks)
- Active Task Count (Tasks must drain back to baseline)
- Event Loop Lag (Average lag must remain < 15 ms).

---

## 3. Preflight Execution Command

To execute the automated release gate verification preflight check:

```bash
python scripts/release_gate.py
```
