"""Tests for RSS feed generation."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree.ElementTree import fromstring
from unittest.mock import patch

from podcraft.feed import build_rss, format_rfc822
from podcraft.config import PodcraftConfig, PodcastConfig, FeedConfig


@pytest.fixture
def feed_config():
    return PodcraftConfig(
        podcast=PodcastConfig(
            title="Test Podcast",
            description="A test podcast.",
            author="Tester",
            language="en",
            category="Technology",
            link="https://example.com",
            cover_url="https://example.com/cover.png",
        ),
        feed=FeedConfig(audio_base_url="https://example.com/audio"),
    )


def test_format_rfc822():
    dt = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    result = format_rfc822(dt)
    assert "03 Apr 2026" in result
    assert "+0800" in result


@patch("podcraft.feed.get_duration", return_value=600.0)
def test_build_rss_structure(mock_duration, feed_config, tmp_path):
    # Create a dummy audio file
    audio_file = tmp_path / "ep01.mp3"
    audio_file.write_bytes(b"\x00" * 1000)

    tz = timezone(timedelta(hours=8))
    episodes = [{
        "title": "EP01: Test Episode",
        "description": "A test episode description.",
        "audio_file": str(audio_file),
        "audio_url": "https://example.com/audio/ep01.mp3",
        "pub_date": datetime(2026, 4, 3, 12, 0, 0, tzinfo=tz),
        "episode_number": 1,
    }]

    xml = build_rss(episodes, feed_config)

    assert '<?xml version="1.0"' in xml
    assert "<title>Test Podcast</title>" in xml
    assert "<title>EP01: Test Episode</title>" in xml
    assert "A test episode description." in xml
    assert "https://example.com/audio/ep01.mp3" in xml
    assert "cover.png" in xml


@patch("podcraft.feed.get_duration", return_value=0)
def test_build_rss_multiple_episodes(mock_duration, feed_config, tmp_path):
    tz = timezone(timedelta(hours=8))
    episodes = []
    for i in range(3):
        audio_file = tmp_path / f"ep{i + 1:02d}.mp3"
        audio_file.write_bytes(b"\x00" * 500)
        episodes.append({
            "title": f"EP{i + 1:02d}: Episode {i + 1}",
            "description": f"Description {i + 1}",
            "audio_file": str(audio_file),
            "audio_url": f"https://example.com/audio/ep{i + 1:02d}.mp3",
            "pub_date": datetime(2026, 4, i + 1, tzinfo=tz),
            "episode_number": i + 1,
        })

    xml = build_rss(episodes, feed_config)
    assert xml.count("<item>") == 3


@patch("podcraft.feed.get_duration", return_value=0)
def test_build_rss_empty_episodes(mock_duration, feed_config):
    xml = build_rss([], feed_config)
    assert "<title>Test Podcast</title>" in xml
    assert "<item>" not in xml
