"""Tests for TTS engine factory and audio utilities."""

import pytest
from unittest.mock import patch

from podcraft.tts import create_engine
from podcraft.tts.edge import EdgeTTSEngine
from podcraft.config import PodcraftConfig, TTSConfig


def test_create_edge_engine(sample_config):
    engine = create_engine(sample_config)
    assert isinstance(engine, EdgeTTSEngine)


def test_create_unknown_engine():
    config = PodcraftConfig(tts=TTSConfig(engine="nonexistent"))
    with pytest.raises(ValueError, match="Unknown TTS engine"):
        create_engine(config)


def test_create_volcano_engine_no_creds():
    config = PodcraftConfig(tts=TTSConfig(engine="volcano_podcast"))
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="VOLCANO_PODCAST_APP_ID"):
            create_engine(config)


def test_edge_engine_voices(sample_config):
    engine = EdgeTTSEngine(sample_config)
    assert engine.voices["host"] == "en-US-GuyNeural"
    assert engine.voices["guest"] == "en-US-JennyNeural"
