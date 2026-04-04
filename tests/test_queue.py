"""Tests for publish queue management."""

import json
import pytest
from pathlib import Path

from podcraft.queue import load_queue, get_next, pop_queue, push_queue, queue_length


@pytest.fixture
def queue_file(tmp_path):
    path = tmp_path / "publish-queue.json"
    items = [
        {"episode": 7, "title": "EP07: Topic A", "research_file": "episodes/ep07.md", "season": 1},
        {"episode": 8, "title": "EP08: Topic B", "research_file": "episodes/ep08.md", "season": 1},
    ]
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    return path


def test_load_queue(queue_file):
    items = load_queue(queue_file)
    assert len(items) == 2
    assert items[0]["episode"] == 7


def test_load_queue_missing_file(tmp_path):
    items = load_queue(tmp_path / "nonexistent.json")
    assert items == []


def test_get_next(queue_file):
    item = get_next(queue_file)
    assert item["episode"] == 7
    # File not modified
    assert queue_length(queue_file) == 2


def test_get_next_empty_queue(tmp_path):
    q = tmp_path / "q.json"
    assert get_next(q) is None


def test_pop_queue(queue_file):
    item = pop_queue(queue_file)
    assert item["episode"] == 7
    assert queue_length(queue_file) == 1
    # Next item is now episode 8
    next_item = get_next(queue_file)
    assert next_item["episode"] == 8


def test_pop_queue_until_empty(queue_file):
    pop_queue(queue_file)
    pop_queue(queue_file)
    assert pop_queue(queue_file) is None
    assert queue_length(queue_file) == 0


def test_push_queue(queue_file):
    push_queue(queue_file, {"episode": 9, "title": "EP09: Topic C"})
    items = load_queue(queue_file)
    assert len(items) == 3
    assert items[-1]["episode"] == 9


def test_push_to_new_file(tmp_path):
    q = tmp_path / "new-queue.json"
    push_queue(q, {"episode": 1, "title": "EP01"})
    assert queue_length(q) == 1


def test_queue_preserves_content(queue_file):
    pop_queue(queue_file)
    remaining = load_queue(queue_file)
    assert remaining[0]["title"] == "EP08: Topic B"
    assert remaining[0]["research_file"] == "episodes/ep08.md"
