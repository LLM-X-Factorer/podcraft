"""Publish queue management: FIFO JSON queue for episode scheduling."""

import json
from pathlib import Path

QUEUE_FILENAME = "publish-queue.json"


def load_queue(queue_path: Path) -> list[dict]:
    """Load the publish queue from a JSON file. Returns empty list if file doesn't exist."""
    if not queue_path.exists():
        return []
    return json.loads(queue_path.read_text(encoding="utf-8"))


def get_next(queue_path: Path) -> dict | None:
    """Peek at the first item in the queue without removing it."""
    items = load_queue(queue_path)
    return items[0] if items else None


def pop_queue(queue_path: Path) -> dict | None:
    """Remove and return the first item from the queue. Updates the file."""
    items = load_queue(queue_path)
    if not items:
        return None
    item = items.pop(0)
    queue_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def push_queue(queue_path: Path, item: dict) -> None:
    """Append an item to the end of the queue."""
    items = load_queue(queue_path)
    items.append(item)
    queue_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def queue_length(queue_path: Path) -> int:
    """Return the number of items in the queue."""
    return len(load_queue(queue_path))
