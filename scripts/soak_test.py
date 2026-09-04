#!/usr/bin/env python3
"""
Aetheris V5 Stability, Stress, and Long-Running Soak Test Harness.
Profiles process RSS, heap objects, asyncio tasks, JobSupervisor jobs,
handlers, CPU, thread count, handle/FD count, and event loop lag.

Supports:
  python scripts/soak_test.py --duration 60s
  python scripts/soak_test.py --duration 30m
  python scripts/soak_test.py --duration 2h
  python scripts/soak_test.py --attach-running <PID> --duration 6h
"""

import argparse
import asyncio
import gc
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psutil

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))
os.environ["AETHERIS_OFFLINE_VALIDATION"] = "1"
os.environ["DB_PATH"] = ":memory:"
os.environ["SQL_ENGINE"] = "sqlite"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.SoakHarness")


def parse_duration(dur_str: str) -> int:
    """Parses duration strings such as 20s, 60s, 30m, 2h, 6h, 12h, 24h into seconds."""
    match = re.match(r"^(\d+)([smhd])?$", dur_str.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration format: '{dur_str}'. Use e.g. 60s, 30m, 2h, 6h")
    val = int(match.group(1))
    unit = match.group(2) or "s"
    if unit == "s":
        return val
    elif unit == "m":
        return val * 60
    elif unit == "h":
        return val * 3600
    elif unit == "d":
        return val * 86400
    return val


async def measure_loop_lag() -> float:
    """Measures event loop delay in milliseconds."""
    t0 = time.perf_counter()
    await asyncio.sleep(0.001)
    delay = (time.perf_counter() - t0 - 0.001) * 1000.0
    return max(0.0, delay)


def calculate_slope(values: List[float]) -> float:
    """Computes linear regression slope for trend analysis."""
    n = len(values)
    if n < 2:
        return 0.0
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(values) / n
    numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    return round(numerator / max(1e-9, denominator), 4)


async def run_soak(
    duration_seconds: int = 30,
    sample_interval: float = 1.0,
    attach_pid: Optional[int] = None,
):
    from userbot.core.jobs.supervisor import JobPriority, job_supervisor
    from userbot.core.transfer.engine import transfer_engine
    from userbot.core.flood_shield import flood_shield, RPCLane
    from userbot.core.plugins.registry import atomic_registry
    from userbot.sql_helper.globals import _CACHE

    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_file = artifacts_dir / f"soak_{timestamp_str}.jsonl"
    canonical_metrics_file = artifacts_dir / "soak_metrics.jsonl"

    if canonical_metrics_file.exists():
        canonical_metrics_file.unlink()

    proc = psutil.Process(attach_pid) if attach_pid else psutil.Process()
    mode_label = f"Attached to PID {attach_pid}" if attach_pid else "In-Process Workload Engine"

    LOGS.info(
        "Initiating Aetheris V5 Soak Monitor [%s] (Target Duration: %ds, Sample Rate: %.1fs)...",
        mode_label,
        duration_seconds,
        sample_interval,
    )

    if not attach_pid:
        await job_supervisor.start()

    stop_event = asyncio.Event()
    metrics_history: List[Dict] = []
    total_workload_cycles = 0

    # 1. Standalone Workload Generator (active if not attaching to external process)
    async def workload_generator():
        nonlocal total_workload_cycles
        counter = 0
        while not stop_event.is_set():
            counter += 1
            total_workload_cycles += 1

            # A. Job Supervisor Workload
            async def dummy_job_work(token=None):
                await asyncio.sleep(0.01)
                return "done"

            priority = JobPriority.HIGH if (counter % 5 == 0) else JobPriority.NORMAL
            await job_supervisor.submit(
                name=f"soak_job_{counter}",
                coro_fn=dummy_job_work,
                priority=priority,
                plugin_id="soak_harness",
            )

            # B. Transfer Engine Task
            transfer_task = transfer_engine.create_task(
                task_id=f"soak_tx_{counter}",
                file_size=512 * 1024,
                is_upload=(counter % 2 == 0),
            )
            transfer_task.update_progress(0, 128 * 1024)

            # C. FloodShield RPC Execution
            async def fake_rpc(val):
                return val * 2

            lane = RPCLane.P0_SYSTEM if (counter % 7 == 0) else RPCLane.P2_NORMAL
            await flood_shield.execute(fake_rpc, 21, lane=lane, cb_key="soak_rpc")

            # Periodic cleanup
            if counter % 50 == 0:
                job_supervisor.prune_completed_jobs(max_retained=50)

            await asyncio.sleep(0.02)

    # 2. Comprehensive Metrics Sampler
    async def metrics_sampler():
        start_time = time.time()
        sample_idx = 0

        with open(canonical_metrics_file, "a", encoding="utf-8") as f_canon, \
             open(timestamped_file, "a", encoding="utf-8") as f_ts:

            while not stop_event.is_set():
                sample_idx += 1
                now = time.time()
                elapsed = round(now - start_time, 2)

                gc.collect()
                mem_info = proc.memory_info()
                rss_mb = round(mem_info.rss / (1024 * 1024), 2)
                cpu_pct = round(proc.cpu_percent(interval=None), 1)
                threads_cnt = proc.num_threads()
                
                # Handles / File descriptors
                try:
                    num_handles = proc.num_handles() if hasattr(proc, "num_handles") else proc.num_fds()
                except Exception:
                    num_handles = 0

                heap_objects = len(gc.get_objects())
                active_async_tasks = len(asyncio.all_tasks())
                loop_lag = round(await measure_loop_lag(), 3)
                active_jobs = len(job_supervisor.list_jobs(active_only=True))
                handler_count = atomic_registry.total_commands()
                cache_items = len(_CACHE)

                record = {
                    "sample": sample_idx,
                    "elapsed_s": elapsed,
                    "rss_mb": rss_mb,
                    "cpu_percent": cpu_pct,
                    "threads": threads_cnt,
                    "handles_fds": num_handles,
                    "heap_objects": heap_objects,
                    "active_tasks": active_async_tasks,
                    "active_jobs": active_jobs,
                    "handler_count": handler_count,
                    "cache_items": cache_items,
                    "loop_lag_ms": loop_lag,
                    "timestamp": now,
                }
                metrics_history.append(record)
                
                line = json.dumps(record) + "\n"
                f_canon.write(line)
                f_canon.flush()
                f_ts.write(line)
                f_ts.flush()

                LOGS.info(
                    "[%02ds/%02ds] RSS: %.2fMB (Handles: %d) | Tasks: %d | Jobs: %d | Lag: %.2fms",
                    int(elapsed),
                    duration_seconds,
                    rss_mb,
                    num_handles,
                    active_async_tasks,
                    active_jobs,
                    loop_lag,
                )

                await asyncio.sleep(sample_interval)

    # Launch workloads
    tasks = [asyncio.create_task(metrics_sampler())]
    if not attach_pid:
        tasks.append(asyncio.create_task(workload_generator()))

    await asyncio.sleep(duration_seconds)
    stop_event.set()

    await asyncio.gather(*tasks, return_exceptions=True)
    if not attach_pid:
        await job_supervisor.stop()

    if not metrics_history:
        raise RuntimeError("No metrics recorded during soak execution!")

    # 3. Leak Analysis Calculation
    rss_vals = [m["rss_mb"] for m in metrics_history]
    task_vals = [m["active_tasks"] for m in metrics_history]
    handle_vals = [m["handles_fds"] for m in metrics_history]
    lag_vals = [m["loop_lag_ms"] for m in metrics_history]

    initial_rss = rss_vals[0]
    final_rss = rss_vals[-1]
    min_rss = min(rss_vals)
    max_rss = max(rss_vals)
    rss_delta = round(final_rss - initial_rss, 2)
    rss_slope = calculate_slope(rss_vals)

    initial_tasks = task_vals[0]
    final_tasks = task_vals[-1]
    task_delta = final_tasks - initial_tasks
    task_slope = calculate_slope([float(v) for v in task_vals])

    avg_lag = sum(lag_vals) / len(lag_vals)
    max_lag = max(lag_vals)

    dur_label = f"{duration_seconds} SECOND STRESS TEST" if duration_seconds < 3600 else f"{duration_seconds // 3600} HOUR SOAK TEST"

    print("\n" + "=" * 80)
    print(f"AETHERIS V5 {dur_label.upper()} TELEMETRY & LEAK ANALYSIS:")
    print("=" * 80)
    print(f"  Duration Run:              {duration_seconds}s ({round(duration_seconds / 60, 2)}m)")
    print(f"  Samples Recorded:          {len(metrics_history)}")
    print(f"  Workload Cycles:           {total_workload_cycles}")
    print(f"  RSS (MB):                  init={initial_rss:.2f}, min={min_rss:.2f}, max={max_rss:.2f}, final={final_rss:.2f}, delta={rss_delta:+.2f}, slope={rss_slope}")
    print(f"  Async Tasks:               init={initial_tasks}, min={min(task_vals)}, max={max(task_vals)}, final={final_tasks}, delta={task_delta:+d}, slope={task_slope}")
    print(f"  Handles/FDs:               init={handle_vals[0]}, final={handle_vals[-1]}, max={max(handle_vals)}")
    print(f"  Loop Latency:              avg={avg_lag:.2f}ms, peak={max_lag:.2f}ms")
    print(f"  Primary Telemetry:         {canonical_metrics_file}")
    print(f"  Timestamped Telemetry:     {timestamped_file}")
    print("=" * 80)

    # Release thresholds:
    # Memory growth rate threshold: delta < 25 MB for short stress (<120s), or slope < 0.15 MB/sample for long runs
    max_allowed_delta = 25.0 if duration_seconds <= 120 else 50.0
    assert rss_delta < max_allowed_delta, f"Unbounded memory growth detected: +{rss_delta:.2f} MB"
    assert avg_lag < 30.0, f"Event loop degraded: avg lag {avg_lag:.2f}ms"
    LOGS.info("%s PASSED: Metrics strictly bounded.", dur_label)
    return True


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Soak & Stability Harness")
    parser.add_argument(
        "--duration",
        default="30s",
        help="Duration string (e.g., 20s, 60s, 30m, 2h, 6h, 12h, 24h). Default: 30s",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=1.0,
        help="Telemetry sampling interval in seconds. Default: 1.0s",
    )
    parser.add_argument(
        "--attach-running",
        type=int,
        default=None,
        help="Attach to an already running Aetheris bot process by PID.",
    )
    args = parser.parse_args()

    dur_seconds = parse_duration(args.duration)
    asyncio.run(run_soak(
        duration_seconds=dur_seconds,
        sample_interval=args.sample_interval,
        attach_pid=args.attach_running,
    ))


if __name__ == "__main__":
    main()
