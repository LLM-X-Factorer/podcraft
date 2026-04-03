"""Audio post-processing: silence, concatenation, loudness normalization."""

import subprocess
import tempfile
from pathlib import Path


def create_silence(duration: float, output_path: str, sample_rate: int = 44100):
    """Create a silence audio file."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", str(duration),
        "-c:a", "libmp3lame", "-q:a", "9",
        output_path,
    ], capture_output=True, check=True)


def concatenate_with_silence(segment_files: list[str], silence_path: str, output_path: str):
    """Concatenate audio segments with silence gaps between them."""
    concat_list = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    abs_silence = str(Path(silence_path).resolve())
    for i, seg in enumerate(segment_files):
        abs_seg = str(Path(seg).resolve())
        concat_list.write(f"file '{abs_seg}'\n")
        if i < len(segment_files) - 1:
            concat_list.write(f"file '{abs_silence}'\n")
    concat_list.close()

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list.name,
        "-c", "copy",
        output_path,
    ], capture_output=True, check=True)

    Path(concat_list.name).unlink()


def normalize_loudness(input_path: str, output_path: str, sample_rate: int = 44100, bitrate: str = "192k"):
    """Normalize audio to podcast standard loudness (-16 LUFS)."""
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", str(sample_rate),
        "-ac", "2",
        "-c:a", "libmp3lame",
        "-b:a", bitrate,
        output_path,
    ], capture_output=True, check=True)
