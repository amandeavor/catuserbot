# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


class MetricsCollector:
    """
    High-performance, lock-free/low-contention metrics accumulator for Aetheris V5.
    Calculates command latencies (p50, p95, p99), throughput, error rates, and system resource health.
    """

    def __init__(self, sample_window: int = 500):
        self.sample_window = sample_window
        self.start_time = time.time()
        self.total_commands: int = 0
        self.failed_commands: int = 0
        self.flood_wait_count: int = 0
        self.total_flood_wait_seconds: float = 0.0
        self.bytes_downloaded: int = 0
        self.bytes_uploaded: int = 0

        # Latency samples (in ms) for percentile calculations
        self._latencies: Deque[float] = deque(maxlen=sample_window)
        self._cmd_frequencies: Dict[str, int] = {}

    def record_command(self, name: str, latency_ms: float, success: bool = True) -> None:
        self.total_commands += 1
        if not success:
            self.failed_commands += 1
        self._latencies.append(latency_ms)
        self._cmd_frequencies[name] = self._cmd_frequencies.get(name, 0) + 1

    def record_flood_wait(self, seconds: float) -> None:
        self.flood_wait_count += 1
        self.total_flood_wait_seconds += seconds

    def record_transfer(self, bytes_count: int, is_upload: bool = False) -> None:
        if is_upload:
            self.bytes_uploaded += bytes_count
        else:
            self.bytes_downloaded += bytes_count

    def _calc_percentile(self, sorted_vals: List[float], p: float) -> float:
        if not sorted_vals:
            return 0.0
        idx = int(len(sorted_vals) * p)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    def get_snapshot(self) -> Dict[str, Any]:
        uptime_sec = time.time() - self.start_time
        sorted_lats = sorted(self._latencies) if self._latencies else []

        p50 = self._calc_percentile(sorted_lats, 0.50)
        p95 = self._calc_percentile(sorted_lats, 0.95)
        p99 = self._calc_percentile(sorted_lats, 0.99)

        # Basic process memory
        mem_mb = 0.0
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / (1024 * 1024)
        except Exception:
            pass

        return {
            "uptime_seconds": round(uptime_sec, 1),
            "total_commands": self.total_commands,
            "failed_commands": self.failed_commands,
            "error_rate_pct": round((self.failed_commands / self.total_commands * 100) if self.total_commands > 0 else 0.0, 2),
            "latencies_ms": {
                "p50": round(p50, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
            },
            "flood_waits": {
                "count": self.flood_wait_count,
                "total_seconds": round(self.total_flood_wait_seconds, 1),
            },
            "transfer": {
                "downloaded_mb": round(self.bytes_downloaded / (1024 * 1024), 2),
                "uploaded_mb": round(self.bytes_uploaded / (1024 * 1024), 2),
            },
            "memory_rss_mb": round(mem_mb, 2),
            "top_commands": sorted(self._cmd_frequencies.items(), key=lambda x: x[1], reverse=True)[:5],
        }


metrics = MetricsCollector()
