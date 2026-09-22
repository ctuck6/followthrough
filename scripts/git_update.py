"""Fast-forward a clean checkout before desktop startup."""

import os
import subprocess
from pathlib import Path
from typing import TextIO


def update_checkout(root: Path, log: TextIO) -> bool:
    """Return whether files changed; preserve local edits and divergent branches."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o ConnectTimeout=10"

    def git(*args: str) -> str:
        result = subprocess.run(
            ["/usr/bin/git", *args], cwd=root, env=env,
            capture_output=True, text=True, timeout=30, check=True,
        )
        return result.stdout.strip()

    def note(message: str) -> None:
        log.write(f"Auto-update: {message}\n")
        log.flush()

    try:
        if git("status", "--porcelain", "--untracked-files=normal"):
            note("Skipped: uncommitted changes. Opening the local version.")
            return False
        branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
        remote = git("config", "--get", f"branch.{branch}.remote")
        ref = git("config", "--get", f"branch.{branch}.merge")
        if remote == "." or not ref.startswith("refs/heads/"):
            note("Skipped: no remote tracking branch.")
            return False
        before = git("rev-parse", "HEAD")
        git("fetch", "--no-tags", remote, ref)
        target = git("rev-parse", "FETCH_HEAD")
        if before == target:
            note("Already up to date.")
            return False
        # Recheck after fetching in case the editor saved during the network call.
        if git("status", "--porcelain", "--untracked-files=normal"):
            note("Skipped: local files changed while checking for updates.")
            return False
        if git("symbolic-ref", "--quiet", "--short", "HEAD") != branch:
            note("Skipped: the checked-out branch changed.")
            return False
        if git("rev-parse", "HEAD") != before:
            note("Skipped: the local commit changed.")
            return False
        git("merge-base", "--is-ancestor", "HEAD", target)
        git("merge", "--ff-only", target)
        note(f"Updated {branch}: {before[:8]} → {target[:8]}.")
        return True
    except (OSError, subprocess.SubprocessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        note(f"Update unavailable; opening the local version. {detail.strip()}")
        return False
