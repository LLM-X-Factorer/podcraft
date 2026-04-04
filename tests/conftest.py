"""Shared test fixtures."""

import pytest
from pathlib import Path

from podcraft.config import (
    PodcraftConfig, PodcastConfig, HostConfig, LLMConfig, TTSConfig, FeedConfig,
    CoverConfig, ShowNotesConfig, ReleaseConfig,
)


@pytest.fixture
def sample_config():
    return PodcraftConfig(
        podcast=PodcastConfig(title="Test Podcast", language="en", author="Tester"),
        host=HostConfig(name="Alice", voice="en-US-GuyNeural"),
        guest=HostConfig(name="Bob", voice="en-US-JennyNeural"),
        llm=LLMConfig(engine="gemini"),
        tts=TTSConfig(engine="edge", silence_duration=1.0),
        feed=FeedConfig(audio_base_url="https://example.com/audio"),
    )


@pytest.fixture
def sample_dialogue():
    return [
        {"role": "host", "text": "Hey Bob, what's the Pomodoro Technique?"},
        {"role": "guest", "text": "It's a time management method using 25-minute work intervals."},
        {"role": "host", "text": "That sounds simple. Does it actually work?"},
        {"role": "guest", "text": "Yes! It leverages timeboxing and forced breaks to maintain focus."},
    ]


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with podcraft.yaml."""
    config_content = """
podcast:
  title: "Test Podcast"
  language: "en"
  author: "Tester"

hosts:
  host:
    name: "Alice"
  guest:
    name: "Bob"

llm:
  engine: "gemini"

tts:
  engine: "edge"
  silence_duration: 1.0

feed:
  audio_base_url: "https://example.com/audio"
"""
    (tmp_path / "podcraft.yaml").write_text(config_content, encoding="utf-8")
    (tmp_path / "output").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "prompts").mkdir()
    return tmp_path
