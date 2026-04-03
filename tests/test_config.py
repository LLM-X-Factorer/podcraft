"""Tests for configuration loading."""

import pytest
from pathlib import Path

from podcraft.config import load_config, PodcraftConfig, DEFAULT_VOICES, find_config


def test_load_config_from_yaml(tmp_project):
    config, root = load_config(tmp_project / "podcraft.yaml")
    assert config.podcast.title == "Test Podcast"
    assert config.podcast.language == "en"
    assert config.host.name == "Alice"
    assert config.guest.name == "Bob"
    assert root == tmp_project


def test_default_voices_applied(tmp_project):
    config, _ = load_config(tmp_project / "podcraft.yaml")
    assert config.host.voice == DEFAULT_VOICES["en"]["host"]
    assert config.guest.voice == DEFAULT_VOICES["en"]["guest"]


def test_chinese_voices(tmp_path):
    (tmp_path / "podcraft.yaml").write_text("""
podcast:
  language: "zh-cn"
hosts:
  host:
    name: "小刘"
  guest:
    name: "美美"
""", encoding="utf-8")
    config, _ = load_config(tmp_path / "podcraft.yaml")
    assert config.host.voice == DEFAULT_VOICES["zh"]["host"]
    assert config.guest.voice == DEFAULT_VOICES["zh"]["guest"]


def test_custom_voice_not_overridden(tmp_path):
    (tmp_path / "podcraft.yaml").write_text("""
podcast:
  language: "en"
hosts:
  host:
    name: "Alex"
    voice: "custom-voice-id"
""", encoding="utf-8")
    config, _ = load_config(tmp_path / "podcraft.yaml")
    assert config.host.voice == "custom-voice-id"


def test_resolve_paths(sample_config):
    root = Path("/tmp/myproject")
    paths = sample_config.resolve_paths(root)
    assert paths["output"] == (root / "output").resolve()
    assert paths["scripts"] == (root / "scripts").resolve()


def test_missing_config_raises():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/podcraft.yaml"))


def test_empty_yaml(tmp_path):
    (tmp_path / "podcraft.yaml").write_text("", encoding="utf-8")
    config, _ = load_config(tmp_path / "podcraft.yaml")
    # Should use all defaults
    assert config.podcast.title == "My Podcast"
    assert config.tts.engine == "edge"


def test_get_voices_unknown_language():
    config = PodcraftConfig()
    config.podcast.language = "fr"
    voices = config.get_voices()
    # Falls back to English
    assert voices["host"] == DEFAULT_VOICES["en"]["host"]
