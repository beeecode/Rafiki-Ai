from __future__ import annotations

import webbrowser
from urllib.parse import urlparse


def open_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only http:// and https:// URLs are allowed.")
    opened = webbrowser.open(url)
    if not opened:
        raise RuntimeError("The operating system did not accept the URL open request.")
    return f"Opened URL: {url}"
