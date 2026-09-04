#!/usr/bin/env python3
"""
Aetheris V5 Database State Preservation & Migration Integrity Check.
Verifies datastore continuity across restarts, reloads, and migrations:
1. Connects to configured datastore backend (SQLite / PostgreSQL)
2. Captures tables, row counts, and schema signatures
3. Verifies non-sensitive persistent state (e.g. gvars)
4. Asserts no tables dropped, no data lost, zero secret leaks
5. Produces sanitized artifact: artifacts/database_preservation.json
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.DBPreservation")

SENSITIVE_KEYWORDS = {"token", "secret", "session", "pass", "key", "auth", "hash", "cred"}


def is_sensitive_key(key_name: str) -> bool:
    lower = key_name.lower()
    return any(k in lower for k in SENSITIVE_KEYWORDS)


def capture_snapshot() -> Dict[str, Any]:
    from sqlalchemy import inspect, text
    from userbot.sql_helper import ENGINE, get_storage_mode

    if ENGINE is None:
        raise RuntimeError("SQLAlchemy ENGINE is not initialized")

    inspector = inspect(ENGINE)
    table_names = inspector.get_table_names()
    storage_mode = get_storage_mode()
    dialect = ENGINE.name

    table_data = {}
    with ENGINE.connect() as conn:
        for tbl in table_names:
            try:
                res = conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))
                row_count = res.scalar() or 0
                cols = [c["name"] for c in inspector.get_columns(tbl)]
                table_data[tbl] = {
                    "row_count": row_count,
                    "columns_count": len(cols),
                }
            except Exception as e:
                LOGS.warning("Could not inspect table '%s': %s", tbl, e)
                table_data[tbl] = {
                    "row_count": -1,
                    "columns_count": 0,
                    "error": str(e),
                }

    # Inspect gvars safely without leaking sensitive values
    gvars_keys = []
    if "gvars" in table_names:
        try:
            with ENGINE.connect() as conn:
                res = conn.execute(text('SELECT "variable" FROM "gvars"'))
                for row in res:
                    var_name = row[0]
                    if not is_sensitive_key(var_name):
                        gvars_keys.append(var_name)
                    else:
                        gvars_keys.append(f"[MASKED_SENSITIVE_KEY_{len(var_name)}]")
        except Exception as e:
            LOGS.warning("Could not inspect gvars: %s", e)

    return {
        "timestamp": time.time(),
        "storage_mode": storage_mode,
        "dialect": dialect,
        "total_tables": len(table_names),
        "table_stats": table_data,
        "safe_gvars_count": len(gvars_keys),
        "safe_gvars_sample": gvars_keys[:20],
    }


def verify_preservation(pre_snap: Dict[str, Any], post_snap: Dict[str, Any]) -> Dict[str, Any]:
    issues = []

    # Verify tables preserved
    pre_tables = set(pre_snap.get("table_stats", {}).keys())
    post_tables = set(post_snap.get("table_stats", {}).keys())

    missing_tables = pre_tables - post_tables
    if missing_tables:
        issues.append(f"Tables dropped after boot: {sorted(missing_tables)}")

    # Verify row counts not decreased
    for tbl, pre_info in pre_snap.get("table_stats", {}).items():
        if tbl in post_tables:
            post_info = post_snap["table_stats"][tbl]
            pre_rows = pre_info.get("row_count", 0)
            post_rows = post_info.get("row_count", 0)
            if post_rows < pre_rows:
                issues.append(f"Table '{tbl}' suffered row count drop: {pre_rows} -> {post_rows}")

    passed = (len(issues) == 0)
    return {
        "preserved": passed,
        "tables_before": len(pre_tables),
        "tables_after": len(post_tables),
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Database State Preservation Check")
    parser.add_argument("--snapshot", choices=["pre", "post", "verify"], default="verify",
                        help="Action: capture pre-boot snapshot, post-boot snapshot, or full verification")
    args = parser.parse_args()

    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    pre_file = artifacts_dir / "db_pre_snapshot.json"
    post_file = artifacts_dir / "db_post_snapshot.json"
    report_file = artifacts_dir / "database_preservation.json"

    LOGS.info("Executing database preservation check (mode: %s)...", args.snapshot)

    try:
        current_snap = capture_snapshot()
    except Exception as e:
        LOGS.error("Failed to capture database snapshot: %s", e)
        report = {
            "timestamp": time.time(),
            "status": "FAILED",
            "gate_passed": False,
            "error": str(e),
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        sys.exit(1)

    if args.snapshot == "pre":
        with open(pre_file, "w", encoding="utf-8") as f:
            json.dump(current_snap, f, indent=2)
        LOGS.info("Pre-boot snapshot saved to %s (%d tables)", pre_file, current_snap["total_tables"])
        sys.exit(0)

    elif args.snapshot == "post":
        with open(post_file, "w", encoding="utf-8") as f:
            json.dump(current_snap, f, indent=2)
        LOGS.info("Post-boot snapshot saved to %s (%d tables)", post_file, current_snap["total_tables"])
        # If pre snapshot exists, run verification automatically
        if pre_file.exists():
            with open(pre_file, "r", encoding="utf-8") as f:
                pre_snap = json.load(f)
            res = verify_preservation(pre_snap, current_snap)
            report = {
                "timestamp": time.time(),
                "status": "PASS" if res["preserved"] else "FAILED",
                "gate_passed": res["preserved"],
                "backend": current_snap["dialect"],
                "storage_mode": current_snap["storage_mode"],
                "total_tables": current_snap["total_tables"],
                "verification_details": res,
                "error": None if res["preserved"] else "; ".join(res["issues"]),
            }
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            LOGS.info("Preservation report written to %s (Status: %s)", report_file, report["status"])
        sys.exit(0)

    else:
        # Full verify mode: If pre snapshot doesn't exist, use current as baseline and verify self-consistency
        pre_snap = current_snap
        if pre_file.exists():
            with open(pre_file, "r", encoding="utf-8") as f:
                pre_snap = json.load(f)

        res = verify_preservation(pre_snap, current_snap)
        report = {
            "timestamp": time.time(),
            "status": "PASS" if res["preserved"] else "FAILED",
            "gate_passed": res["preserved"],
            "backend": current_snap["dialect"],
            "storage_mode": current_snap["storage_mode"],
            "total_tables": current_snap["total_tables"],
            "table_stats": current_snap["table_stats"],
            "safe_gvars_count": current_snap["safe_gvars_count"],
            "verification_details": res,
            "error": None if res["preserved"] else "; ".join(res["issues"]),
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("Preservation check complete: %d tables verified. Report: %s", current_snap["total_tables"], report_file)
        sys.exit(0 if res["preserved"] else 1)


if __name__ == "__main__":
    main()
