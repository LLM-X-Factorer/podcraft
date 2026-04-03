"""TTS engine abstraction."""

from .edge import EdgeTTSEngine
from .audio import create_silence, concatenate_with_silence, normalize_loudness


def create_engine(config):
    """Factory: create the appropriate TTS engine from config."""
    engine_name = config.tts.engine
    if engine_name == "edge":
        return EdgeTTSEngine(config)
    elif engine_name == "volcano_podcast":
        from .volcano_podcast import VolcanoPodcastEngine
        return VolcanoPodcastEngine(config)
    else:
        raise ValueError(f"Unknown TTS engine: {engine_name}. Use 'edge' or 'volcano_podcast'.")
