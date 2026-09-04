# Changelog

All notable changes to the **Aetheris** platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.0.0] - 2026-09-04

### Architectural Upgrade: Aetheris V4 to Aetheris V5
A complete architectural redesign of the core automation engine while preserving 100% backward compatibility for all 139 legacy user plugins.

### Added
- **Transport Abstraction Layer (`userbot.core.transport`)**:
  - `TransportInterface` decoupling high-level automation from underlying MTProto client implementations.
  - `TelethonAdapter` providing seamless translation for Telethon event loops.
  - `MockAdapter` providing zero-network simulated MTProto runtime for unit and integration testing.
- **Generational Plugin Architecture (`userbot.core.plugins`)**:
  - `PluginManifest` schema for strongly-typed metadata, dependency validation, and capability declaration.
  - `PluginGeneration` isolating runtime state, handler bindings, and active tasks.
  - `AtomicHandlerRegistry` enabling zero-downtime hot-reloading with atomic pointer swaps (`atomic_swap_generation`).
  - `VersionedPluginManager` executing a 16-step transactional reload process with zero-loss rollback.
- **Resilient Concurrency & Supervision (`userbot.core.jobs`)**:
  - `JobSupervisor` managing background coroutines with structured concurrency.
  - `CancellationToken` providing hierarchical cancellation, timeout traps, and cooperative polling.
  - Four priority scheduling tiers: `CRITICAL`, `HIGH`, `NORMAL`, `BACKGROUND`.
- **FloodShield V5 & BlastGuard (`userbot.core.flood_shield`, `userbot.core.blast_guard`)**:
  - Four segregated RPC priority lanes (`CRITICAL`, `HIGH`, `NORMAL`, `BULK`).
  - State-machine driven `CircuitBreaker` (`CLOSED`, `OPEN`, `HALF_OPEN`).
  - Token bucket rate limiting preventing burst-induced flood bans.
  - Exponential jitter backoff on MTProto `FloodWaitError`.
- **POSIX-Compliant Command Parser (`userbot.core.parser`)**:
  - Streaming `CommandLexer` supporting single/double bash quoting and escape sequences.
  - `CommandParserV5` extracting positional arguments, long flags (`--key=val`), short flags (`-f`), and clustered flags (`-rfv`).
  - Automatic type coercion for boolean, integer, and float flag values.
- **High-Throughput Chunk Transfer & Media Engine (`userbot.core.transfer`, `userbot.core.media`)**:
  - `ChunkPlanner` optimizing chunk sizes from 128KB to 1024KB with up to 16 parallel workers.
  - `MediaServiceV5` providing async media probing, auto-thumbnail extraction, and transcoding.
- **Polyglot AI Fabric (`userbot.core.ai`)**:
  - Unified multi-provider engine supporting Google Gemini, OpenAI, Anthropic Claude, and local Ollama models.
  - Provider fallback cascading on 429 rate limits or 503 outages.
  - Sliding context memory with token thresholds and conversation compaction.
- **Cryptographic Callback Security (`userbot.core.callbacks`)**:
  - `SecureCallbackManager` generating HMAC-SHA256 opaque callback tokens.
  - Millisecond-resolution replay protection and scope authorization matching initiator user IDs.
- **Web Control Plane & Observability (`userbot.core.web`, `userbot.core.observability`)**:
  - `DashboardServer` providing a high-performance web dashboard with real-time SSE metrics streaming.
  - High-contrast Linear/Raycast dark mode UI.
  - Microsecond-resolution distributed span tracing via `AetherisTracer`.
  - Comprehensive metrics aggregation engine (`MetricsEngine`).
- **Comprehensive Test Suite & Benchmarks**:
  - Complete automated test suite under `tests/` covering AI routing, callbacks, flood protection, jobs, parser, plugin lifecycle, storage caching, and transfer chunking.
  - `benchmarks/benchmark_suite.py` measuring parser throughput (65.5k ops/s), registry lookup (2.43M ops/s), and cache read latency (0.52 us).

### Changed
- **Database Storage Engine (`userbot.sql_helper`)**:
  - Added two-tier storage with an in-memory TTL write-through cache for global variables (`addgvar`, `gvarstatus`).
  - Added automatic zero-configuration failover to SQLite WAL storage (`sqlite:///aetheris.db`) when external PostgreSQL is unreachable.
- **Legacy Command Parser Bridge (`userbot.helpers.utils.flags`)**:
  - Reimplemented `parse_flag` using `CommandParserV5` while retaining 100% backward compatibility for all legacy plugin signatures.
- **Core Client & Runner (`userbot/core/client.py`, `userbot/__main__.py`)**:
  - Integrated distributed tracing into every incoming message and outbound RPC request.
  - Attached V5 subsystem instances (`supervisor`, `callback_manager`, `flood_shield`, `tracer`, `dashboard`) directly to `CatUserBotClient`.

### Fixed
- Fixed variable shadowing in `userbot/helpers/__init__.py` where `check = 0` shadowed imported helper functions.
- Guarded optional binary and scraping dependencies (`lxml_html_clean`, `pillow`, `wand`, `cinemagoer`) to prevent startup crashes when libraries are missing in lightweight environments.
