# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import re
import time
from typing import Dict, List, Tuple

from userbot.core.parser import command_parser
from userbot.core.plugins.registry import HandlerBinding, atomic_registry
from userbot.core.transfer.engine import ChunkPlanner
from userbot.sql_helper.globals import Globals, SESSION, addgvar, gvarstatus


# ============================================================================
# 1. PARSER MICROBENCHMARK: V4 Naive Regex/Split vs V5 Streaming Lexer
# ============================================================================

def _legacy_v4_parse(text: str) -> Tuple[Dict[str, str], List[str]]:
    """Equivalent to legacy V4 parse_arguments implementation in flags.py."""
    flags = {}
    positional = []
    tokens = text.split()
    for t in tokens:
        if t.startswith("--"):
            parts = t[2:].split("=", 1)
            flags[parts[0]] = parts[1] if len(parts) > 1 else "True"
        elif t.startswith("-") and len(t) > 1:
            flags[t[1:]] = "True"
        else:
            positional.append(t)
    return flags, positional


def benchmark_parser(iterations: int = 20000) -> dict:
    test_commands = [
        '.echo "hello world" --times=3 -v',
        '.deploy web-service production --replicas 5 -f --dry-run',
        '.clean -rfv /var/log/temp',
        '.scale api --count 8 --rate 2.5 --strict',
        '.ask "explain quantum computing in simple terms" --provider=claude --temp 0.2',
    ]

    # Measure Legacy V4 baseline on same hardware and data
    t0_v4 = time.perf_counter()
    for i in range(iterations):
        cmd_str = test_commands[i % len(test_commands)]
        _ = _legacy_v4_parse(cmd_str)
    dur_v4 = time.perf_counter() - t0_v4
    throughput_v4 = iterations / dur_v4

    # Measure V5 POSIX Streaming Lexer
    t0_v5 = time.perf_counter()
    for i in range(iterations):
        cmd_str = test_commands[i % len(test_commands)]
        _ = command_parser.parse(cmd_str)
    dur_v5 = time.perf_counter() - t0_v5
    throughput_v5 = iterations / dur_v5

    return {
        "category": "Microbenchmark - Parser Throughput",
        "iterations": iterations,
        "v4_throughput_ops_sec": round(throughput_v4, 2),
        "v4_avg_latency_us": round((dur_v4 / iterations) * 1_000_000, 2),
        "v5_throughput_ops_sec": round(throughput_v5, 2),
        "v5_avg_latency_us": round((dur_v5 / iterations) * 1_000_000, 2),
        "notes": "V5 provides full POSIX bash quoting, escapes, and typed flag normalization.",
    }


# ============================================================================
# 2. REGISTRY MICROBENCHMARK: Handler Lookup & Generational Atomic Swap
# ============================================================================

def benchmark_registry_and_swap(iterations: int = 50000) -> dict:
    def dummy_handler(event):
        return True

    # Register 100 sample commands
    for i in range(100):
        atomic_registry.register(f"cmd_{i}", dummy_handler, generation_id=1)

    # 1. Lookup latency
    t0 = time.perf_counter()
    for i in range(iterations):
        _ = atomic_registry.get_handler_for_command(f"cmd_{i % 100}")
    lookup_duration = time.perf_counter() - t0
    lookup_throughput = iterations / lookup_duration

    # 2. Generational swap timing (Zero-downtime hot-reload)
    swap_bindings = [
        HandlerBinding(command_name=f"cmd_{i}", handler=dummy_handler, generation_id=2)
        for i in range(100)
    ]
    t0_swap = time.perf_counter()
    for _ in range(1000):
        atomic_registry.atomic_swap_generation(1, 2, swap_bindings)
        atomic_registry.atomic_swap_generation(2, 1, swap_bindings)
    swap_duration = time.perf_counter() - t0_swap
    avg_swap_us = (swap_duration / 2000) * 1_000_000

    return {
        "category": "Microbenchmark - Registry Handler Lookup & Swap",
        "lookup_throughput_ops_sec": round(lookup_throughput, 2),
        "lookup_avg_latency_us": round((lookup_duration / iterations) * 1_000_000, 3),
        "v5_100_handler_swap_latency_us": round(avg_swap_us, 2),
        "v4_swap_latency": "N/A (V4 required full process restart to reload handlers)",
    }


# ============================================================================
# 3. TRANSFER MICROBENCHMARK: ChunkPlanner Calculation
# ============================================================================

def benchmark_chunk_planner(iterations: int = 50000) -> dict:
    sizes = [
        1024 * 512,                # 512 KB
        15 * 1024 * 1024,          # 15 MB
        250 * 1024 * 1024,         # 250 MB
        1500 * 1024 * 1024,        # 1.5 GB
    ]

    t0 = time.perf_counter()
    for i in range(iterations):
        sz = sizes[i % len(sizes)]
        _ = ChunkPlanner.plan_chunks(sz)
    duration = time.perf_counter() - t0

    throughput = iterations / duration

    return {
        "category": "Microbenchmark - File Transfer ChunkPlanner Speed",
        "iterations": iterations,
        "throughput_ops_sec": round(throughput, 2),
        "avg_latency_us": round((duration / iterations) * 1_000_000, 3),
        "notes": "Guarantees strict 512 KiB MTProto cap across all file sizes.",
    }


# ============================================================================
# 4. STORAGE BENCHMARK: In-Memory L1 Cache vs Direct Database L2 Query
# ============================================================================

def benchmark_storage(iterations: int = 5000) -> dict:
    addgvar("bench_storage_key", "aetheris_val")

    # In-memory L1 cache read
    t0_cache = time.perf_counter()
    for _ in range(iterations):
        _ = gvarstatus("bench_storage_key")
    dur_cache = time.perf_counter() - t0_cache
    cache_throughput = iterations / dur_cache

    # Direct L2 database read (uncached SQL roundtrip)
    t0_db = time.perf_counter()
    for _ in range(iterations):
        row = SESSION.query(Globals).filter(Globals.variable == "bench_storage_key").first()
        _ = row.value if row else None
        SESSION.close()
    dur_db = time.perf_counter() - t0_db
    db_throughput = iterations / dur_db

    return {
        "category": "Storage Benchmark - In-Memory Cache (L1) vs Direct SQL (L2)",
        "iterations": iterations,
        "l1_cache_throughput_ops_sec": round(cache_throughput, 2),
        "l1_cache_latency_us": round((dur_cache / iterations) * 1_000_000, 3),
        "l2_direct_sql_throughput_ops_sec": round(db_throughput, 2),
        "l2_direct_sql_latency_us": round((dur_db / iterations) * 1_000_000, 3),
    }


def run_all_benchmarks():
    print("=" * 70)
    print("[*] A E T H E R I S  V 5  --  R I G O R O U S  B E N C H M A R K S [*]")
    print("=" * 70)

    p = benchmark_parser()
    print(f"[*] {p['category']}")
    print(f"    - V4 Baseline (Naive Split): {p['v4_throughput_ops_sec']:,} ops/s ({p['v4_avg_latency_us']} us)")
    print(f"    - V5 Streaming Lexer:       {p['v5_throughput_ops_sec']:,} ops/s ({p['v5_avg_latency_us']} us)")
    print(f"    - Note: {p['notes']}\n")

    r = benchmark_registry_and_swap()
    print(f"[*] {r['category']}")
    print(f"    - V5 Lookup Throughput:      {r['lookup_throughput_ops_sec']:,} ops/s ({r['lookup_avg_latency_us']} us)")
    print(f"    - V5 100-Handler Swap:       {r['v5_100_handler_swap_latency_us']} us")
    print(f"    - V4 Swap Latency:           {r['v4_swap_latency']}\n")

    c = benchmark_chunk_planner()
    print(f"[*] {c['category']}")
    print(f"    - Throughput:                {c['throughput_ops_sec']:,} ops/s")
    print(f"    - Latency:                   {c['avg_latency_us']} us\n")

    s = benchmark_storage()
    print(f"[*] {s['category']}")
    print(f"    - L1 In-Memory Cache:        {s['l1_cache_throughput_ops_sec']:,} ops/s ({s['l1_cache_latency_us']} us)")
    print(f"    - L2 Direct SQL (Uncached):  {s['l2_direct_sql_throughput_ops_sec']:,} ops/s ({s['l2_direct_sql_latency_us']} us)\n")

    print("=" * 70)
    print("[+] All Benchmarks Executed on Identical Hardware & Interpreter [+]")
    print("=" * 70)


if __name__ == "__main__":
    run_all_benchmarks()
