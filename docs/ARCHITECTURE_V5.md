# Aetheris V5 Architecture Specification

## 1. Executive Summary

**Aetheris V5** represents a complete architectural evolution of the Aetheris MTProto automation engine (formerly CatUserBot). While retaining 100% backward compatibility for all 139 legacy user plugins, V5 transitions the platform from a monolithic, tightly-coupled scripting bot into a **modular, resilient, high-throughput, and fully observable Telegram automation platform**.

### Core Tenets of V5
- **Atomic Plugin Hot-Reloading**: Atomically swapping plugin generations to prevent handler loss and orphan tasks.
- **Strict MTProto Flood Protection**: Lane-segmented token buckets, circuit breakers, and exponential jitter backoff (`FloodShieldV5`).
- **Deterministic Command Parsing**: POSIX-compliant streaming lexer and grammar parser with bash-style quoting and typed flag extraction.
- **Resilient Background Execution**: Structured concurrency with job supervision, hierarchical cancellation tokens, and priority tiers.
- **Provider-Agnostic Intelligence**: Multi-provider AI fabric with automatic fallback and sliding context memory.
- **Cryptographic Security**: HMAC-SHA256 opaque callback payload validation with millisecond-resolution replay protection.
- **Comprehensive Observability**: Microsecond-resolution distributed span tracing and real-time dashboard instrumentation.

---

## 2. High-Level System Architecture

```mermaid
flowchart TB
    subgraph Telegram MTProto Network
        TG[Telegram Gateways / DCs]
    end

    subgraph Transport & Ingestion Layer
        TA[TelethonAdapter / MockAdapter]
        FS[FloodShield V5 & BlastGuard]
        TR[Aetheris Distributed Tracer]
    end

    subgraph Command & Dispatch Engine
        LEX[POSIX Lexer & CommandParserV5]
        REG[AtomicHandlerRegistry (Generational)]
        VPM[VersionedPluginManager]
    end

    subgraph Concurrency & Execution Core
        JOB[JobSupervisor & Priority Engine]
        XFER[FileTransferEngineV5 (Parallel Chunks)]
        MEDIA[MediaServiceV5 Pipeline]
        AI[AIRouterV5 Polyglot Engine]
    end

    subgraph State & Security Layer
        SEC[SecureCallbackManager (HMAC-SHA256)]
        CACHE[TTL In-Memory Cache]
        SQL[Resilient SQL Storage (SQLite / PostgreSQL)]
    end

    subgraph Control & Observability
        DASH[DashboardServer (Async Web / SSE)]
        METRICS[Metrics Collector Engine]
    end

    TG <--> TA
    TA <--> FS
    FS --> TR
    TR --> LEX
    LEX --> REG
    VPM --> REG
    REG --> JOB
    JOB --> XFER
    JOB --> MEDIA
    JOB --> AI
    TA <--> SEC
    REG <--> CACHE
    CACHE <--> SQL
    METRICS --> DASH
    TR --> DASH
```

---

## 3. Core Subsystems

### 3.1 MTProto Transport Abstraction
- **Module**: `userbot.core.transport`
- **Interfaces**:
  - `TransportInterface`: Abstract protocol defining connection lifecycle (`connect`, `disconnect`), raw invocation (`invoke`), high-level messaging (`send_message`, `edit_message`, `delete_messages`), and event listener dispatch (`add_event_handler`, `remove_event_handler`).
  - `TelethonAdapter`: Wraps Telethon's `TelegramClient`, mapping MTProto RPC requests directly into typed responses.
  - `MockAdapter`: In-memory simulated MTProto client designed for deterministic unit and integration testing without network IO or API token dependencies.

### 3.2 Versioned Plugin Lifecycle & Zero-Downtime Hot-Reload
- **Module**: `userbot.core.plugins`
- **Components**:
  - `PluginManifest`: Strongly-typed schema validating plugin names, semver versions, dependencies, and capability tags.
  - `PluginGeneration`: Encapsulates a specific runtime generation of an instantiated plugin, isolating its bound handlers, tasks, and state.
  - `AtomicHandlerRegistry`: Thread-safe handler registry using generational IDs. Enables zero-downtime hot-reloads via `atomic_swap_generation(old_gen, new_gen, new_bindings)`.
  - `VersionedPluginManager`: Implements a 16-step atomic migration transaction:
    1. Validate plugin file and schema.
    2. Allocate target generation ID ($G_{k+1}$).
    3. Load module in isolated execution sandbox.
    4. Validate and compile handler decorators.
    5. Register new generation handlers in standby mode.
    6. Execute `on_plugin_pre_reload()` hook on active generation ($G_k$).
    7. Capture and serialize mutable state via `export_plugin_state()`.
    8. Initialize target generation ($G_{k+1}$) with serialized state.
    9. Verify target generation health check.
    10. Execute atomic pointer swap in `AtomicHandlerRegistry`.
    11. Issue graceful `CancellationToken` to tasks bound to $G_k$.
    12. Wait up to grace period (5000ms) for $G_k$ task completion.
    13. Force-terminate orphaned tasks in $G_k$.
    14. Execute `on_plugin_unload()` on $G_k$.
    15. Purge $G_k$ from module registry and garbage-collect resources.
    16. Emit telemetry event `plugin.reload.success`. If any step fails before step 10, the system triggers a zero-loss rollback to $G_k$.

### 3.3 Concurrency & Resilient Job Supervision
- **Module**: `userbot.core.jobs.supervisor`
- **Components**:
  - `JobSupervisor`: Global scheduler and lifecycle manager for all asynchronous background coroutines.
  - `CancellationToken`: Hierarchical cancellation tokens supporting parent-child token cascades, cooperative polling (`is_cancelled`), and timeout traps.
  - `JobPriority`: 4-tier scheduling priority (`CRITICAL`, `HIGH`, `NORMAL`, `BACKGROUND`).
  - `JobState`: Finite state machine tracking (`PENDING` -> `RUNNING` -> `COMPLETED` / `FAILED` / `CANCELLED`).
  - **Supervision**: Emits heartbeats, detects stalled tasks, captures uncaught exceptions, and triggers configured restart policies (`NEVER`, `ON_FAILURE`, `ALWAYS`).

### 3.4 FloodShield V5 & BlastGuard
- **Module**: `userbot.core.flood_shield` & `userbot.core.blast_guard`
- **Traffic Segregation (RPC Lanes)**:
  - `CRITICAL`: Security alerts, admin kill commands, session termination.
  - `HIGH`: Direct user commands and interactive replies.
  - `NORMAL`: Broadcast messaging, status updates, periodic syncs.
  - `BULK`: Media downloads/uploads, bulk scraping, message purging.
- **Circuit Breaker**: 3-state state machine (`CLOSED` -> `OPEN` -> `HALF_OPEN`) tracking rolling failure ratios. Automatically fast-fails requests when MTProto limits are threatened.
- **Token Bucket Rate Limiter**: Independent rate buckets per lane and peer ID preventing burst-induced FloodWait cascades and transport instability.
- **Exponential Jitter Backoff**: Adds decorrelated random jitter to wait durations when handling `FloodWaitError`.

### 3.5 POSIX-Compliant Command Parser
- **Module**: `userbot.core.parser`
- **Architecture**:
  - `CommandLexer`: Zero-copy character streaming tokenizer recognizing words, single quotes (`'...'`), double quotes (`"..."`), escape characters (`\`), flags, and key-value options.
  - `CommandParserV5`: Grammar parser turning raw Telegram messages into structured `ParsedCommand` dataclasses.
  - **Flag Normalization**:
    - Long flags: `--force`, `--dry-run`, `--name="Aetheris V5"`
    - Short flags: `-f`, `-v`, `-n "Value"`
    - Clustered short flags: `-rfv` expands automatically into `-r`, `-f`, `-v`.
    - Typed value parsing: Automatic conversion of string tokens into booleans, integers, floats, and strings.

### 3.6 Parallel Chunk Transfer & Media Processing
- **Modules**: `userbot.core.transfer` & `userbot.core.media`
- **ChunkPlanner**:
  - Dynamic chunk sizing from 128 KB up to 1024 KB based on payload size.
  - Up to 16 parallel part workers for large files.
  - Progress tracking with EWMA speed smoothing and ETA estimation.
- **MediaServiceV5**:
  - Asynchronous probe (`probe_media`) for dimensions, bitrate, and duration.
  - Auto-thumbnail extraction using `ffmpeg` with fallback to Pillow.
  - Asynchronous audio transcoding and video normalization pipeline.

### 3.7 Polyglot AI Fabric
- **Module**: `userbot.core.ai`
- **Features**:
  - Unified interface across **Google Gemini**, **OpenAI**, **Anthropic Claude**, and local **Ollama** models.
  - Fallback cascades: Automatically attempts secondary and tertiary providers upon rate-limit (429) or service outages (503).
  - Sliding context memory with token threshold enforcement and in-memory message history compaction.

### 3.8 Cryptographic Opaque Callbacks
- **Module**: `userbot.core.callbacks`
- **Mechanisms**:
  - HMAC-SHA256 token generation: Callback data encodes `action:opaque_token`.
  - Nonce and timestamp validation preventing replay attacks.
  - Strict TTL expiration (default 300s).
  - Scope isolation verifying that user ID clicking the inline button matches the initiating commander.

### 3.9 Observability & Web Dashboard
- **Modules**: `userbot.core.observability` & `userbot.core.web`
- **AetherisTracer**: High-resolution monotonic span tracing recording duration, tags, errors, and parent-child causal relationships.
- **MetricsEngine**: Real-time counter, gauge, and histogram metric aggregation.
- **DashboardServer**: Minimal-dependency `aiohttp` web control panel styled with dark mode, high-contrast typographic hierarchy, real-time memory/CPU metrics, and live SSE log streaming.

---

## 4. State Management & Storage Layer
- Multi-tier storage:
  - **Tier 1 (L1 Cache)**: High-performance in-memory dictionary with TTL expiration and automatic eviction.
  - **Tier 2 (L2 Persistent)**: PostgreSQL when `DB_URI` is specified; automatic zero-configuration fallback to SQLite (`aetheris.db`) with WAL mode when PostgreSQL is offline or unconfigured.
