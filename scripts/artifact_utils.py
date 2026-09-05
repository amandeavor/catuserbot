#!/usr/bin/env python3
"""
Aetheris V5 Acceptance Artifact Utilities.
Binds every generated acceptance artifact to the exact Git commit, branch, platform,
and timestamp, ensuring strict integrity and preventing artifact reuse across code modifications.
"""

import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).parent.parent.resolve()
AETHERIS_VERSION = "5.0.0-rc2"


def get_git_commit() -> str:
    """Retrieve the full 40-character SHA of current Git HEAD."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception as e:
        return "UNKNOWN_COMMIT"


def get_git_branch() -> str:
    """Retrieve the active Git branch name."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_BRANCH"


def is_git_tree_clean() -> bool:
    """Check if Git working tree has no unstaged/uncommitted changes."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return len(res.stdout.strip()) == 0
    except Exception:
        return False


def get_standard_metadata(test_name: str, result: str = "PASS") -> Dict[str, Any]:
    """
    Generate standard provenance metadata for test artifacts.
    Guarantees strict binding to current commit, python version, and UTC timestamp.
    """
    return {
        "git_commit": get_git_commit(),
        "git_branch": get_git_branch(),
        "aetheris_version": AETHERIS_VERSION,
        "test_name": test_name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "result": result,
        "git_tree_clean": is_git_tree_clean(),
    }


def validate_artifact(
    artifact_data: Dict[str, Any],
    expected_commit: Optional[str] = None,
    allow_skipped: bool = False,
) -> tuple[bool, str]:
    """
    Validates that an artifact belongs to the current HEAD commit and reflects a PASS result.
    Rejects SKIPPED, NOT_RUN, PARTIAL, FAILED, ERROR, or mismatched commit hashes.
    """
    if not isinstance(artifact_data, dict):
        return False, "Artifact is not a valid JSON dictionary"

    art_commit = artifact_data.get("git_commit")
    curr_commit = expected_commit or get_git_commit()

    if not isinstance(curr_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", curr_commit):
        return False, "Current commit is not a verified Git SHA"
    if not isinstance(art_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", art_commit):
        return False, "Artifact commit is not a verified Git SHA"

    if not art_commit or art_commit != curr_commit:
        return False, f"Artifact commit mismatch: artifact was produced at {art_commit[:8] if art_commit else 'NONE'}, but current HEAD is {curr_commit[:8]}"

    if artifact_data.get("git_tree_clean") is not True:
        return False, "Artifact was not produced from a verified clean tree"
    res = artifact_data.get("result", artifact_data.get("status", ""))
    invalid_states = {"SKIPPED", "SKIPPED_CREDENTIALS_ABSENT", "NOT_RUN", "PARTIAL", "FAILED", "ERROR"}

    if res in invalid_states:
        if allow_skipped and "SKIPPED" in res:
            return True, "Artifact is in skipped state (permissible in pre-live evaluation)"
        return False, f"Artifact result is not PASS (found: '{res}')"

    if res != "PASS":
        return False, f"Artifact result is not verified PASS (found: '{res}')"
    if "status" in artifact_data and artifact_data["status"] != "PASS":
        return False, "Artifact has conflicting status"
    if "gate_passed" in artifact_data and artifact_data["gate_passed"] is not True:
        return False, "Artifact has conflicting gate result"

    return True, "Artifact validated successfully"
