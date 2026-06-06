from __future__ import annotations

import subprocess


def open_app_command(command: str) -> None:
    subprocess.Popen(
        ["open", "-a", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
