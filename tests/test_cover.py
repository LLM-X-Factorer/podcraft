"""Tests for cover image generation."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from podcraft.config import PodcraftConfig, PodcastConfig, CoverConfig
from podcraft.cover import create_cover_engine, PlaceholderCoverEngine, ImagenCoverEngine


@pytest.fixture
def cover_config():
    return PodcraftConfig(
        podcast=PodcastConfig(title="Test Podcast", language="en"),
        cover=CoverConfig(engine="placeholder", size=200),
    )


def test_factory_disabled(cover_config):
    cover_config.cover.engine = "disabled"
    assert create_cover_engine(cover_config) is None


def test_factory_placeholder(cover_config):
    engine = create_cover_engine(cover_config)
    assert isinstance(engine, PlaceholderCoverEngine)


def test_factory_imagen(cover_config):
    cover_config.cover.engine = "imagen"
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        engine = create_cover_engine(cover_config)
    assert isinstance(engine, ImagenCoverEngine)


def test_factory_unknown(cover_config):
    cover_config.cover.engine = "unknown_engine"
    with pytest.raises(ValueError, match="Unknown cover engine"):
        create_cover_engine(cover_config)


def test_imagen_requires_api_key(cover_config):
    cover_config.cover.engine = "imagen"
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("GEMINI_API_KEY", None)
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            ImagenCoverEngine(cover_config)


@pytest.mark.integration
def test_placeholder_generates_image(cover_config, tmp_path):
    pytest.importorskip("PIL")
    engine = PlaceholderCoverEngine(cover_config)
    out = tmp_path / "cover.png"
    result = engine.generate("EP01: Test Episode", 1, out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_cover_config_defaults():
    config = PodcraftConfig()
    assert config.cover.engine == "disabled"
    assert config.cover.size == 1400
    assert config.cover.overlay == {}
    assert config.cover.theme_keywords == {}


def test_cover_config_from_yaml(tmp_path):
    from podcraft.config import load_config
    yaml_content = """
podcast:
  title: "My Pod"
  language: "en"
cover:
  engine: "placeholder"
  size: 800
  overlay:
    title: "My Pod"
    subtitle: "Subtitle"
    title_color: [255, 0, 0]
"""
    config_path = tmp_path / "podcraft.yaml"
    config_path.write_text(yaml_content)
    config, root = load_config(config_path)
    assert config.cover.engine == "placeholder"
    assert config.cover.size == 800
    assert config.cover.overlay["title"] == "My Pod"
    assert config.cover.overlay["title_color"] == [255, 0, 0]
