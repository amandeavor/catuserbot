#!/usr/bin/env python3
"""
Aetheris V5 Stable Release Promotion Utility.
CRITICAL SAFETY RULE:
This script must NEVER be executed automatically by CI, test harnesses, or AI agents.
It exists solely for explicit invocation by the human user/operator after personally
completing real-world Telegram usage validation.

Strict Gates Enforced:
1. Clean Git Working Tree (git status --porcelain == 0)
2. Matching Git HEAD (Manifest commit == current HEAD commit)
3. 100% Automated Gates Verified PASS
4. 100% Live MTProto & Transfer Acceptance Evidence Verified PASS
5. Explicit Operator Confirmation Token (--confirm-operator-validation)
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from scripts.artifact_utils import get_git_commit, is_git_tree_clean

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.Promotion")


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Stable Release Promotion Guard")
    parser.add_argument(
        "--confirm-operator-validation",
        type=str,
        help="Explicit confirmation token from human operator indicating real usage was tested and passed",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("AETHERIS V5 STABLE RELEASE PROMOTION GUARD")
    print("=" * 80)

    # 1. Working tree cleanliness gate
    if not is_git_tree_clean():
        LOGS.critical(
            "PROMOTION_BLOCKED [DIRTY_TREE]: Git working tree contains modified or untracked files. "
            "The code tested must be exactly the code released."
        )
        sys.exit(1)

    curr_head = get_git_commit()
    LOGS.info("Current Git HEAD commit: %s", curr_head)

    # 2. Manifest verification gate
    manifest_file = ROOT_DIR / "artifacts" / "final_acceptance_manifest.json"
    if not manifest_file.exists():
        LOGS.critical(
            "PROMOTION_BLOCKED [MANIFEST_MISSING]: artifacts/final_acceptance_manifest.json does not exist. "
            "Run full test and live qualification suite first."
        )
        sys.exit(1)

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest.get("git_commit") != curr_head:
        LOGS.critical(
            "PROMOTION_BLOCKED [COMMIT_MISMATCH]: Manifest commit (%s) does not match current HEAD (%s)!",
            manifest.get("git_commit", "NONE")[:8],
            curr_head[:8],
        )
        sys.exit(1)

    # 3. Acceptance Evidence Verification
    required_passes = [
        "automated_tests",
        "plugin_runtime",
        "command_registry",
        "secret_scan",
        "database_preservation",
        "session_preservation",
        "basic_mtproto",
        "live_transfer",
        "live_hotreload",
    ]
    for gate in required_passes:
        val = manifest.get(gate)
        if val != "PASS":
            LOGS.critical(
                "PROMOTION_BLOCKED [INCOMPLETE_EVIDENCE]: Gate '%s' has result '%s' (PASS required).",
                gate,
                val,
            )
            sys.exit(1)

    # 4. Explicit Operator Confirmation Gate
    expected_token = "OPERATOR_CONFIRMED_REAL_WORLD_USAGE"
    if args.confirm_operator_validation != expected_token:
        print("\n" + "!" * 80)
        print("PROMOTION_BLOCKED [OPERATOR_VALIDATION_REQUIRED]")
        print("!" * 80)
        print("Stable promotion requires explicit manual confirmation from the operator.")
        print("Automated and live MTProto test passes are necessary evidence, but NOT a substitute")
        print("for real user testing with an active Telegram account.")
        print("")
        print("To promote after verifying normal userbot operation:")
        print(f"  python scripts/promote_stable.py --confirm-operator-validation {expected_token}")
        print("!" * 80 + "\n")
        sys.exit(1)

    # 5. Execute explicit promotion
    LOGS.info("All technical gates and operator validation confirmed. Promoting to 5.0.0 STABLE...")
    manifest["operator_validation"] = "PASS"
    manifest["stable_promotion_eligible"] = True
    manifest["version"] = "5.0.0"

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "=" * 80)
    print("STATUS: AETHERIS 5.0.0 OFFICIALLY PROMOTED TO STABLE")
    print(f"Git HEAD: {curr_head}")
    print("=" * 80)
    sys.exit(0)


if __name__ == "__main__":
    main()
