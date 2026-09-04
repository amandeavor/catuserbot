# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from typing import Any, Dict, List, Optional, Tuple
import logging

LOGS = logging.getLogger("Aetheris.BlastGuard")


class BlastGuardException(Exception):
    """Raised when an operation exceeds safety thresholds without explicit confirmation."""
    def __init__(self, action: str, count: int, threshold: int, suggestion: str):
        self.action = action
        self.count = count
        self.threshold = threshold
        self.suggestion = suggestion
        super().__init__(
            f"BlastGuard: Operation '{action}' would affect {count} entities (Safety threshold: {threshold}). {suggestion}"
        )


class BlastGuard:
    """
    Safety controller preventing catastrophic accidental bulk operations.
    Enforces explicit confirmation or --force parameters on destructive or high-volume actions.
    """

    def __init__(
        self,
        max_batch_recipients: int = 50,
        max_batch_deletes: int = 100,
        max_mass_invites: int = 25,
    ):
        self.max_batch_recipients = max_batch_recipients
        self.max_batch_deletes = max_batch_deletes
        self.max_mass_invites = max_mass_invites

    def verify_action(
        self,
        action: str,
        count: int,
        force: bool = False,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Validates whether a batch operation is safe to proceed.
        Returns: (allowed: bool, warning_message: str)
        """
        threshold = self.max_batch_recipients
        if "delete" in action:
            threshold = self.max_batch_deletes
        elif "invite" in action:
            threshold = self.max_mass_invites

        if dry_run:
            return False, f"DRY-RUN: Action '{action}' would affect {count} items (Threshold: {threshold})."

        if count > threshold and not force:
            raise BlastGuardException(
                action=action,
                count=count,
                threshold=threshold,
                suggestion="Use '--force' or '-f' flag to confirm and proceed with this operation.",
            )

        if count > threshold and force:
            LOGS.warning("BlastGuard override: Action '%s' proceeding with %d items via --force", action, count)
            return True, f"BlastGuard override: Proceeding with {count} items."

        return True, "Safe to proceed"


blast_guard = BlastGuard()
