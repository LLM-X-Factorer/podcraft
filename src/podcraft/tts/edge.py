"""Edge TTS engine - free, no API key required."""

import asyncio
from pathlib import Path

import edge_tts

from ..config import PodcraftConfig
from .audio import create_silence, concatenate_with_silence, normalize_loudness


class EdgeTTSEngine:
    def __init__(self, config: PodcraftConfig):
        self.config = config
        self.voices = config.get_voices()

    async def synthesize_dialogue(self, dialogue: list[dict], output_path: str) -> dict:
        """Synthesize full dialogue to a single audio file."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        segments_dir = output.parent / "segments" / output.stem
        segments_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Synthesize each turn
        segment_files = []
        total = len(dialogue)
        for i, turn in enumerate(dialogue):
            voice = self.voices[turn["role"]]
            filepath = segments_dir / f"seg_{i:04d}_{turn['role']}.mp3"
            print(f"  [{i + 1}/{total}] {turn['role']}: {turn['text'][:40]}...")
            communicate = edge_tts.Communicate(turn["text"], voice)
            await communicate.save(str(filepath))
            segment_files.append(str(filepath))

        # Step 2: Create silence
        silence_path = str(output.parent / "silence.mp3")
        create_silence(
            self.config.tts.silence_duration, silence_path,
            self.config.tts.sample_rate,
        )

        # Step 3: Concatenate
        raw_path = str(output.parent / f"{output.stem}_raw.mp3")
        concatenate_with_silence(segment_files, silence_path, raw_path)

        # Step 4: Normalize loudness
        normalize_loudness(
            raw_path, output_path,
            self.config.tts.sample_rate, self.config.tts.bitrate,
        )

        # Cleanup
        Path(raw_path).unlink(missing_ok=True)

        return {"engine": "edge", "segments": len(segment_files)}
