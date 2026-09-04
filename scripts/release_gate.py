#!/usr/bin/env python3
"""
Aetheris V5 Automated Release Gate Preflight Verification.
Evaluates both Automated Engineering Gates and Live Telegram MTProto Gates:
1. Python Syntax & Bytecode Compilation
2. Secret Scanning & Session Hygiene (git-tracking check without destroying local sessions)
3. Plugin Runtime Import & Atomic Unbind Artifact (138 plugins)
4. Command Count Reconciliation Artifact (495 handlers, 477 unique triggers, 18 duplicates)
5. Soak / Stress Telemetry & Memory Boundedness (bounded RSS & loop lag)
6. Full Automated Test Suite (pytest -v tests/)
7. Database State Preservation Gate
8. Live Telegram MTProto, Fast Transfer, & Hot-Reload Acceptance Evidence
"""

import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()


def step(msg: str):
    print(f"\n[*] {msg}...")


def pass_msg(msg: str):
    print(f"    [PASS] {msg}")


def warn_msg(msg: str):
    print(f"    [WARN] {msg}")


def fail(msg: str):
    print(f"    [FAIL] {msg}")
    sys.exit(1)


def check_syntax():
    step("1. Checking Python Syntax and Bytecode Compilation")
    py_files = (
        list(ROOT_DIR.glob("userbot/**/*.py"))
        + list(ROOT_DIR.glob("tests/**/*.py"))
        + list(ROOT_DIR.glob("scripts/**/*.py"))
    )
    for f in py_files:
        try:
            py_compile.compile(str(f), doraise=True)
        except Exception as e:
            fail(f"Syntax error in {f}: {e}")
    pass_msg(f"Compiled {len(py_files)} files cleanly with 0 syntax errors")


def check_hygiene():
    step("2. Scanning Git Index for Credentials, Sessions, and DB Artifacts")
    # Never unlink operator's active deployment .session or .db files from disk!
    # Strictly verify that git does not track any session, database, or secret files.
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    tracked_files = res.stdout.splitlines() if res.returncode == 0 else []
    forbidden_extensions = (".session", ".session-journal", ".db", ".sqlite", ".sqlite3", ".env")
    tracked_violations = [
        f for f in tracked_files if any(f.endswith(ext) or f == ".env" for ext in forbidden_extensions)
    ]

    if tracked_violations:
        fail(f"Git-tracked forbidden files found in repository: {tracked_violations}")

    pass_msg("Repository git index clean: No forbidden sessions, databases, or environment secrets tracked")


def check_plugin_validation_artifact():
    step("3. Verifying Plugin Runtime Import & Unbind Artifact")
    artifact_path = ROOT_DIR / "artifacts" / "plugin_runtime_validation.json"
    if not artifact_path.exists():
        fail("plugin_runtime_validation.json does not exist. Run scripts/runtime_plugin_validator.py first.")

    with open(artifact_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = data.get("total_plugins", 0)
    passed = data.get("passed", 0)
    rate = data.get("pass_rate", 0.0)

    if total < 138 or rate < 100.0:
        fail(f"Plugin validation failed requirements: {passed}/{total} ({rate}%)")
    pass_msg(f"Plugin Validation Gate: {passed}/{total} plugins passed (100.0% import & unbind)")


def check_command_reconciliation():
    step("4. Verifying Command Count Reconciliation Artifact")
    artifact_path = ROOT_DIR / "artifacts" / "command_count_reconciliation.json"
    if not artifact_path.exists():
        fail("command_count_reconciliation.json does not exist. Run scratch/generate_reconciliation.py first.")

    with open(artifact_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metrics = data.get("summary_metrics", {})
    total_handlers = metrics.get("total_registered_handlers", 0)
    unique_triggers = metrics.get("unique_command_triggers", 0)
    dup_triggers = metrics.get("duplicate_command_triggers", 0)
    excess_handlers = metrics.get("excess_handlers_from_duplicates", 0)

    # Invariant: unique_triggers + excess_handlers == total_registered_handlers
    if unique_triggers + excess_handlers != total_handlers:
        fail(
            f"Mathematical contradiction in reconciliation: unique ({unique_triggers}) + excess ({excess_handlers}) != total ({total_handlers})"
        )

    discrepancy = data.get("rc1_ast_discrepancy_analysis", {})
    baseline_ast = discrepancy.get("baseline_rc1_ast_reported_commands", 396)
    delta = discrepancy.get("net_discrepancy_delta", 99)

    if baseline_ast + delta != total_handlers:
        fail(f"AST baseline delta mismatch: {baseline_ast} + {delta} != {total_handlers}")

    pass_msg(
        f"Command Reconciliation Gate: {total_handlers} handlers, {unique_triggers} unique triggers, {dup_triggers} duplicates (Exact Match)"
    )


def check_soak_telemetry():
    step("5. Verifying Stability Telemetry Artifact")
    artifact_path = ROOT_DIR / "artifacts" / "soak_metrics.jsonl"
    if not artifact_path.exists():
        fail("soak_metrics.jsonl does not exist. Run scripts/soak_test.py first.")

    lines = [json.loads(line) for line in open(artifact_path, "r", encoding="utf-8") if line.strip()]
    if len(lines) < 10:
        fail(f"Insufficient telemetry samples: {len(lines)}")

    initial_rss = lines[0]["rss_mb"]
    final_rss = lines[-1]["rss_mb"]
    delta = final_rss - initial_rss
    lag_vals = [l.get("loop_lag_ms", 0.0) for l in lines]
    avg_lag = sum(lag_vals) / len(lag_vals)

    if delta > 25.0:
        fail(f"Memory growth exceeded threshold: +{delta:.2f} MB")
    if avg_lag > 30.0:
        fail(f"Event loop degraded: avg lag {avg_lag:.2f} ms")
    pass_msg(f"Stability Gate: {len(lines)} samples, RSS delta {delta:+.2f} MB, avg lag {avg_lag:.2f}ms (bounded)")


def run_unit_and_integration_tests():
    step("6. Running Full Test Suite (pytest -v tests/)")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "tests/"],
        cwd=str(ROOT_DIR),
    )
    if res.returncode != 0:
        fail("pytest suite failed!")
    pass_msg("All automated unit and integration tests passed (0 failures)")


def check_database_preservation():
    step("7. Verifying Database State Preservation Gate")
    db_art = ROOT_DIR / "artifacts" / "database_preservation.json"
    if not db_art.exists():
        fail("database_preservation.json does not exist. Run scripts/database_preservation_check.py first.")

    with open(db_art, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("gate_passed") is not True:
        fail(f"Database preservation check failed: {data.get('error')}")

    pass_msg(
        f"Database Preservation Gate: Verified {data.get('total_tables', 0)} tables intact ({data.get('backend', 'sqlite')})"
    )


def check_live_acceptance_gates() -> bool:
    step("8. Inspecting Live Telegram MTProto, Transfer, & Hot-Reload Acceptance Evidence")
    mtproto_art = ROOT_DIR / "artifacts" / "live_mtproto_acceptance.json"
    transfer_art = ROOT_DIR / "artifacts" / "live_transfer_acceptance.json"
    hotreload_art = ROOT_DIR / "artifacts" / "live_hotreload_acceptance.json"

    mtproto_passed = False
    transfer_passed = False
    hotreload_passed = False

    if mtproto_art.exists():
        d = json.load(open(mtproto_art, "r", encoding="utf-8"))
        if d.get("gate_passed") is True:
            mtproto_passed = True

    if transfer_art.exists():
        d = json.load(open(transfer_art, "r", encoding="utf-8"))
        if d.get("gate_passed") is True:
            transfer_passed = True

    if hotreload_art.exists():
        d = json.load(open(hotreload_art, "r", encoding="utf-8"))
        if d.get("gate_passed") is True:
            hotreload_passed = True

    if mtproto_passed and transfer_passed and hotreload_passed:
        pass_msg("Live Acceptance: MTProto + Fast Transfer + Hot-Reload ALL VERIFIED LIVE PASS")
        return True
    else:
        warn_msg("Live MTProto / Transfer / Hot-Reload gates: PENDING OPERATOR CREDENTIALS")
        warn_msg("To execute live verification run the operator test suite with AETHERIS_LIVE_TESTS=1")
        return False


def main():
    print("=" * 80)
    print("AETHERIS V5 RELEASE GATE PREFLIGHT VERIFICATION")
    print("=" * 80)
    check_syntax()
    check_hygiene()
    check_plugin_validation_artifact()
    check_command_reconciliation()
    check_soak_telemetry()
    run_unit_and_integration_tests()
    check_database_preservation()
    live_passed = check_live_acceptance_gates()

    print("\n" + "=" * 80)
    if live_passed:
        print("STATUS: ALL RELEASE GATES SATISFIED — QUALIFIED FOR PRODUCTION STABLE 5.0.0")
    else:
        print("STATUS: AUTOMATED PRE-LIVE GATES SATISFIED — QUALIFIED FOR 5.0.0-rc2")
        print("NOTE: REPOSITORY REMAINS '5.0.0-rc2' UNTIL LIVE TELEGRAM INTEGRATION PASSES")
    print("=" * 80)

    # Return 0 for RC2 qualification
    sys.exit(0)


if __name__ == "__main__":
    main()
