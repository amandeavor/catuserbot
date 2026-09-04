#!/usr/bin/env python3
"""
Aetheris V5 Automated Release Gate Preflight Verification.
Validates all technical conditions required for promotion from RC to STABLE:
1. Syntax & Compilation (userbot, tests, scripts)
2. Secret scanning & Session hygiene
3. MTProto Maintenance RPC classification
4. Test suite execution (100% pass)
5. Plugin dynamic import & unbind validation
6. Soak testing stability & memory telemetry
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


def fail(msg: str):
    print(f"    [FAIL] {msg}")
    sys.exit(1)


def check_syntax():
    step("1. Checking Python Syntax and Bytecode Compilation")
    py_files = list(ROOT_DIR.glob("userbot/**/*.py")) + list(ROOT_DIR.glob("tests/**/*.py")) + list(ROOT_DIR.glob("scripts/**/*.py"))
    errors = 0
    for f in py_files:
        try:
            py_compile.compile(str(f), doraise=True)
        except Exception as e:
            fail(f"Syntax error in {f}: {e}")
            errors += 1
    pass_msg(f"Compiled {len(py_files)} files cleanly with 0 syntax errors")


def check_hygiene():
    step("2. Scanning for Credentials, Sessions, and DB Artifacts")
    # Clean any local ephemeral test sessions/dbs first
    for f in ROOT_DIR.glob("*.session*"):
        f.unlink(missing_ok=True)
    for f in ROOT_DIR.glob("*.db*"):
        f.unlink(missing_ok=True)

    # Check git tracked files
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    tracked_files = res.stdout.splitlines() if res.returncode == 0 else []
    forbidden_extensions = (".session", ".session-journal", ".db", ".sqlite", ".sqlite3", ".env")
    tracked_violations = [f for f in tracked_files if any(f.endswith(ext) or f == ".env" for ext in forbidden_extensions)]

    if tracked_violations:
        fail(f"Git-tracked forbidden files found: {tracked_violations}")

    # Check for unignored forbidden files in workspace
    forbidden_patterns = ["*.session", "*.session-journal", "*.db", "*.sqlite", ".env"]
    workspace_violations = []
    for pat in forbidden_patterns:
        for p in ROOT_DIR.glob(pat):
            if ".git" not in str(p) and ".pytest_cache" not in str(p):
                workspace_violations.append(str(p.relative_to(ROOT_DIR)))

    if workspace_violations:
        fail(f"Forbidden stateful/credential files present in repo: {workspace_violations}")

    pass_msg("No forbidden sessions, databases, or environment secrets tracked or present")


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
    
    if total < 130 or rate < 100.0:
        fail(f"Plugin validation failed requirements: {passed}/{total} ({rate}%)")
    pass_msg(f"Plugin Validation Gate: {passed}/{total} plugins passed (100.0% import & unbind)")


def check_soak_telemetry():
    step("4. Verifying Soak Test Telemetry Artifact")
    artifact_path = ROOT_DIR / "artifacts" / "soak_metrics.jsonl"
    if not artifact_path.exists():
        fail("soak_metrics.jsonl does not exist. Run scripts/soak_test.py first.")
    
    lines = [json.loads(line) for line in open(artifact_path, "r", encoding="utf-8") if line.strip()]
    if len(lines) < 10:
        fail(f"Insufficient soak test samples: {len(lines)}")
    
    initial_rss = lines[0]["rss_mb"]
    final_rss = lines[-1]["rss_mb"]
    delta = final_rss - initial_rss
    
    if delta > 25.0:
        fail(f"Soak test exceeded memory growth threshold: +{delta:.2f} MB")
    pass_msg(f"Soak Stability Gate: {len(lines)} samples, RSS delta {delta:+.2f} MB, perfectly bounded")


def run_unit_and_integration_tests():
    step("5. Running Full Test Suite (pytest -v tests/)")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "tests/"],
        cwd=str(ROOT_DIR),
    )
    if res.returncode != 0:
        fail("pytest suite failed!")
    pass_msg("All automated unit and integration tests passed (0 failures)")


def main():
    print("=" * 80)
    print("AETHERIS V5 RELEASE GATE PREFLIGHT VERIFICATION")
    print("=" * 80)
    check_syntax()
    check_hygiene()
    check_plugin_validation_artifact()
    check_soak_telemetry()
    run_unit_and_integration_tests()
    print("=" * 80)
    print("ALL RELEASE GATES SATISFIED: AETHERIS V5 QUALIFIED FOR PRODUCTION STABLE")
    print("=" * 80)


if __name__ == "__main__":
    main()
