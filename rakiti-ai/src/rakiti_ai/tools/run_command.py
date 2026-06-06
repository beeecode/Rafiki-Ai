from __future__ import annotations

import getpass
import subprocess
import sys
from pathlib import Path

from rakiti_ai.safety import is_command_allowed, normalize_command


def run_command(command: str, cwd: Path | None = None) -> str:
    if not is_command_allowed(command):
        raise PermissionError("Command is not allowlisted.")

    normalized = normalize_command(command)
    working_dir = cwd or Path.cwd()

    if normalized in {"pwd", "cd"}:
        return str(working_dir)
    if normalized in {"ls", "dir"}:
        entries = sorted(path.name for path in working_dir.iterdir())
        return "\n".join(entries) if entries else "(empty directory)"
    if normalized == "whoami":
        return getpass.getuser()
    if normalized == "python --version":
        return _run([sys.executable, "--version"], working_dir)
    if normalized == "node --version":
        return _run(["node", "--version"], working_dir)
    if normalized == "git status":
        return _run(["git", "status"], working_dir)
    if normalized == "git branch":
        return _run(["git", "branch"], working_dir)
    if normalized == "git log --oneline -5":
        return _run(["git", "log", "--oneline", "-5"], working_dir)

    raise PermissionError("Command is not allowlisted.")


def _run(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(output or f"Command failed with exit code {completed.returncode}.")
    return output
