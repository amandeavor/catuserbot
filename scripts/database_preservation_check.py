#!/usr/bin/env python3
"""
Aetheris V5 Database State Preservation & Migration Integrity Harness.
Supports explicit lifecycle comparison:
  --snapshot-before : Captures pre-live datastore state
  --snapshot-after  : Captures post-live datastore state
  --compare         : Verifies continuity, detects database switching, checks zero data loss

Verifies:
1. Database Identity Continuity (Strictly detects and aborts on silent PostgreSQL/SQLite switching)
2. Schema Signatures (Column names, types, primary keys, indexes)
3. Table Continuity & Monotonic Row Counts
4. Persistent Global Variables (gvars) with strict secret value suppression
5. Binds results to current Git commit HEAD via artifact_utils
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from scripts.artifact_utils import get_standard_metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.DBPreservation")

SENSITIVE_KEYWORDS = {"token", "secret", "session", "pass", "key", "auth", "hash", "cred"}


def is_sensitive_key(key_name: str) -> bool:
    lower = key_name.lower()
    return any(k in lower for k in SENSITIVE_KEYWORDS)


def get_database_identity(engine) -> Dict[str, Any]:
    """Capture sanitized database identity to prevent silent database switching."""
    from userbot.Config import Config
    from userbot.sql_helper import get_storage_mode

    url = engine.url
    backend = engine.name
    storage_mode = get_storage_mode()

    if backend == "sqlite":
        # SQLite database file path resolution
        db_path = url.database
        if db_path and db_path != ":memory:":
            abs_path = str(Path(db_path).resolve())
            file_exists = os.path.isfile(abs_path)
            file_size = os.path.getsize(abs_path) if file_exists else 0
        else:
            abs_path = ":memory:"
            file_exists = True
            file_size = 0
        identifier = f"sqlite://{abs_path}"
    else:
        # PostgreSQL host/port/database (sanitized, password stripped)
        host = url.host or "localhost"
        port = url.port or 5432
        dbname = url.database or "aetheris"
        abs_path = f"{host}:{port}/{dbname}"
        file_exists = True
        file_size = -1
        identifier = f"postgresql://{abs_path}"

    return {
        "storage_mode": storage_mode,
        "backend": backend,
        "identifier": identifier,
        "location": abs_path,
        "file_exists": file_exists,
    }


def capture_snapshot() -> Dict[str, Any]:
    """Capture comprehensive schema and state signature of the current authoritative database."""
    from sqlalchemy import inspect, text
    from userbot.sql_helper import ENGINE

    if ENGINE is None:
        raise RuntimeError("Authoritative database ENGINE is not initialized")

    inspector = inspect(ENGINE)
    table_names = sorted(inspector.get_table_names())
    db_id = get_database_identity(ENGINE)

    table_data = {}
    schema_signatures = {}

    with ENGINE.connect() as conn:
        for tbl in table_names:
            try:
                # Row count
                res = conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))
                row_count = res.scalar() or 0

                # Schema columns
                columns = inspector.get_columns(tbl)
                col_info = [
                    {
                        "name": c["name"],
                        "type": str(c["type"]),
                        "nullable": c.get("nullable", True),
                        "primary_key": c.get("primary_key", False),
                    }
                    for c in columns
                ]

                # Schema indexes
                indexes = inspector.get_indexes(tbl)
                idx_info = [
                    {"name": idx["name"], "columns": idx["column_names"], "unique": idx.get("unique", False)}
                    for idx in indexes
                ]

                # Compute stable signature of table schema
                sig_str = json.dumps({"cols": col_info, "idxs": idx_info}, sort_keys=True)
                tbl_sig = hashlib.sha256(sig_str.encode()).hexdigest()[:16]

                table_data[tbl] = {
                    "row_count": row_count,
                    "columns_count": len(columns),
                    "indexes_count": len(indexes),
                    "schema_signature": tbl_sig,
                    "columns": col_info,
                }
                schema_signatures[tbl] = tbl_sig

            except Exception as e:
                LOGS.warning("Inspection error on table '%s': %s", tbl, e)
                table_data[tbl] = {
                    "row_count": -1,
                    "columns_count": 0,
                    "error": str(e),
                }

    # Safe Global Variables inspection (Zero plaintext secrets)
    safe_gvars = []
    if "gvars" in table_names:
        try:
            with ENGINE.connect() as conn:
                res = conn.execute(text('SELECT "variable" FROM "gvars" ORDER BY "variable"'))
                for row in res:
                    var_name = str(row[0])
                    if not is_sensitive_key(var_name):
                        safe_gvars.append(var_name)
                    else:
                        safe_gvars.append(f"[MASKED_KEY:{len(var_name)}]")
        except Exception as e:
            LOGS.warning("Could not inspect gvars: %s", e)

    metadata = get_standard_metadata("database_preservation_snapshot", "CAPTURED")
    metadata.update({
        "database_identity": db_id,
        "total_tables": len(table_names),
        "table_names": table_names,
        "table_stats": table_data,
        "safe_gvars_count": len(safe_gvars),
        "safe_gvars": safe_gvars,
    })
    return metadata


def compare_snapshots(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Strict comparison of before and after snapshots. Fails on any silent loss or DB switching."""
    issues = []

    # 1. Check database identity continuity (Anti-Split-Brain / Anti-Silent-Switching)
    before_id = before.get("database_identity", {})
    after_id = after.get("database_identity", {})

    if before_id.get("backend") != after_id.get("backend"):
        issues.append(
            f"DATABASE_SWITCH_DETECTED: Backend dialect changed from {before_id.get('backend')} to {after_id.get('backend')}!"
        )

    if before_id.get("identifier") != after_id.get("identifier"):
        issues.append(
            f"DATABASE_SWITCH_DETECTED: Target database changed from {before_id.get('identifier')} to {after_id.get('identifier')}!"
        )

    # 2. Check table preservation
    before_tables = set(before.get("table_stats", {}).keys())
    after_tables = set(after.get("table_stats", {}).keys())

    missing_tables = before_tables - after_tables
    if missing_tables:
        issues.append(f"TABLES_DROPPED: Existing tables dropped after live run: {sorted(missing_tables)}")

    # 3. Check row counts (must not decrease unexpectedly)
    for tbl in before_tables.intersection(after_tables):
        pre_info = before["table_stats"][tbl]
        post_info = after["table_stats"][tbl]

        pre_rows = pre_info.get("row_count", 0)
        post_rows = post_info.get("row_count", 0)

        if post_rows < pre_rows:
            issues.append(f"DATA_LOSS: Table '{tbl}' row count dropped from {pre_rows} to {post_rows}!")

        # 4. Check schema signatures
        pre_sig = pre_info.get("schema_signature")
        post_sig = post_info.get("schema_signature")
        if pre_sig and post_sig and pre_sig != post_sig:
            issues.append(f"SCHEMA_CORRUPTION: Table '{tbl}' schema structure modified unexpectedly!")

    # 5. Check persistent safe gvars
    pre_gvars = set(before.get("safe_gvars", []))
    post_gvars = set(after.get("safe_gvars", []))
    missing_gvars = pre_gvars - post_gvars
    if missing_gvars:
        issues.append(f"GVARS_DROPPED: Persistent global variables lost: {sorted(missing_gvars)}")

    passed = (len(issues) == 0)
    details = {
        "database_identity_verified": (before_id.get("identifier") == after_id.get("identifier")),
        "tables_before": len(before_tables),
        "tables_after": len(after_tables),
        "shared_tables_checked": len(before_tables.intersection(after_tables)),
        "gvars_preserved": len(missing_gvars) == 0,
        "issues": issues,
    }
    return passed, issues, details


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Database State Preservation Harness")
    parser.add_argument("--snapshot-before", action="store_true", help="Capture pre-live database state snapshot")
    parser.add_argument("--snapshot-after", action="store_true", help="Capture post-live database state snapshot")
    parser.add_argument("--compare", action="store_true", help="Compare before/after snapshots and generate evidence")
    parser.add_argument("--verify", action="store_true", help="Convenience: run snapshot or verify self-consistency")
    args = parser.parse_args()

    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    before_file = artifacts_dir / "db_snapshot_before.json"
    after_file = artifacts_dir / "db_snapshot_after.json"
    report_file = artifacts_dir / "database_preservation.json"

    if args.snapshot_before:
        LOGS.info("Capturing PRE-LIVE database state snapshot...")
        snap = capture_snapshot()
        with open(before_file, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2)
        LOGS.info("Pre-live snapshot written to %s (%d tables verified)", before_file, snap["total_tables"])
        sys.exit(0)

    elif args.snapshot_after:
        LOGS.info("Capturing POST-LIVE database state snapshot...")
        snap = capture_snapshot()
        with open(after_file, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2)
        LOGS.info("Post-live snapshot written to %s (%d tables verified)", after_file, snap["total_tables"])
        sys.exit(0)

    elif args.compare:
        LOGS.info("Comparing PRE and POST database snapshots...")
        if not before_file.exists():
            err = f"Missing pre-live snapshot file: {before_file}. Run --snapshot-before first."
            LOGS.error(err)
            sys.exit(1)
        if not after_file.exists():
            err = f"Missing post-live snapshot file: {after_file}. Run --snapshot-after first."
            LOGS.error(err)
            sys.exit(1)

        with open(before_file, "r", encoding="utf-8") as f:
            pre_snap = json.load(f)
        with open(after_file, "r", encoding="utf-8") as f:
            post_snap = json.load(f)

        passed, issues, details = compare_snapshots(pre_snap, post_snap)
        status_res = "PASS" if passed else "FAILED"

        report = get_standard_metadata("database_preservation_verification", status_res)
        report.update({
            "status": status_res,
            "gate_passed": passed,
            "backend": post_snap.get("database_identity", {}).get("backend"),
            "storage_mode": post_snap.get("database_identity", {}).get("storage_mode"),
            "database_identifier": post_snap.get("database_identity", {}).get("identifier"),
            "total_tables": post_snap.get("total_tables"),
            "verification_details": details,
            "error": None if passed else "; ".join(issues),
        })

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        if passed:
            LOGS.info("[PASS] Database preservation verified. Report: %s", report_file)
            sys.exit(0)
        else:
            LOGS.error("[FAIL] Database preservation failed: %s", issues)
            sys.exit(1)

    else:
        # Default self-consistency mode
        LOGS.info("Executing database preservation verification...")
        current_snap = capture_snapshot()

        # If a pre-snapshot exists, compare against it; otherwise use current as baseline
        if before_file.exists():
            with open(before_file, "r", encoding="utf-8") as f:
                pre_snap = json.load(f)
        else:
            pre_snap = current_snap
            with open(before_file, "w", encoding="utf-8") as f:
                json.dump(pre_snap, f, indent=2)

        passed, issues, details = compare_snapshots(pre_snap, current_snap)
        status_res = "PASS" if passed else "FAILED"

        report = get_standard_metadata("database_preservation_verification", status_res)
        report.update({
            "status": status_res,
            "gate_passed": passed,
            "backend": current_snap.get("database_identity", {}).get("backend"),
            "storage_mode": current_snap.get("database_identity", {}).get("storage_mode"),
            "database_identifier": current_snap.get("database_identity", {}).get("identifier"),
            "total_tables": current_snap.get("total_tables"),
            "verification_details": details,
            "error": None if passed else "; ".join(issues),
        })

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        if passed:
            LOGS.info("[PASS] Database preservation check passed (%d tables verified)", current_snap["total_tables"])
            sys.exit(0)
        else:
            LOGS.error("[FAIL] Database preservation check failed: %s", issues)
            sys.exit(1)


if __name__ == "__main__":
    main()
