"""Shared utilities."""

import re
import subprocess
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = re.sub(r'[^\w\u4e00-\u9fff-]', '-', text.lower())
    return re.sub(r'-+', '-', text).strip('-')[:60]


def get_duration(path: str | Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip()) if result.stdout.strip() else 0


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def read_document(path_or_url: str) -> str:
    """Read content from a file path or URL."""
    if path_or_url.startswith("http"):
        import urllib.request
        return urllib.request.urlopen(path_or_url).read().decode("utf-8")
    return Path(path_or_url).read_text(encoding="utf-8")
