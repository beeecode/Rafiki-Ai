from __future__ import annotations

import subprocess


def open_app_command(command: str) -> None:
    subprocess.Popen(
        [command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
