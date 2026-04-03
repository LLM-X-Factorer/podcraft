"""Core pipeline: document → script → audio."""

import asyncio
import json
from pathlib import Path

from .config import PodcraftConfig
from .script import generate_script
from .tts import create_engine
from .utils import slugify, read_document, get_duration


def publish(
    input_path: str,
    config: PodcraftConfig,
    project_root: Path,
    title: str = "",
    episode_num: int = 0,
    focus: str = "",
) -> dict:
    """Full pipeline: document → script → audio. Returns episode metadata."""
    paths = config.resolve_paths(project_root)
    output_dir = paths["output"]
    scripts_dir = paths["scripts"]
    output_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    if not episode_num:
        existing = sorted(output_dir.glob("*.mp3"))
        episode_num = len(existing) + 1

    if not title:
        title = f"EP{episode_num:02d}: {Path(input_path).stem}"

    slug = slugify(title)
    print(f"\n{'=' * 60}")
    print(f"Publishing: {title}")
    print(f"  Source: {input_path}")
    print(f"  Episode: #{episode_num}")
    print(f"{'=' * 60}")

    # Step 1: Read document
    print("\n[1/3] Reading document...")
    content = read_document(input_path)
    if len(content) > 120000:
        print(f"  Truncating from {len(content)} to 120000 chars")
        content = content[:120000]
    print(f"  {len(content)} chars loaded")

    # Step 2: Generate script
    script_path = scripts_dir / f"{slug}_script.json"
    if script_path.exists():
        print(f"\n[2/3] Loading existing script: {script_path}")
        dialogue = json.loads(script_path.read_text(encoding="utf-8"))
    else:
        print("\n[2/3] Generating podcast script...")
        dialogue = generate_script(content, config, project_root, focus)
        script_path.write_text(
            json.dumps(dialogue, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Save human-readable version
        readable_path = script_path.with_suffix(".txt")
        lines = []
        for turn in dialogue:
            name = config.host.name if turn["role"] == "host" else config.guest.name
            lines.append(f"[{name}] {turn['text']}\n")
        readable_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"  {len(dialogue)} dialogue turns")

    # Step 3: Synthesize audio
    audio_path = output_dir / f"{slug}.mp3"
    if audio_path.exists():
        print(f"\n[3/3] Audio already exists: {audio_path}")
    else:
        print(f"\n[3/3] Synthesizing audio ({config.tts.engine})...")
        engine = create_engine(config)
        asyncio.run(engine.synthesize_dialogue(dialogue, str(audio_path)))

    duration = get_duration(audio_path)
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    size_mb = audio_path.stat().st_size / 1024 / 1024
    print(f"  Duration: {minutes}:{seconds:02d}, Size: {size_mb:.1f} MB")

    print(f"\n{'=' * 60}")
    print(f"Done: {title}")
    print(f"  Audio:  {audio_path}")
    print(f"  Script: {script_path}")
    print(f"{'=' * 60}")

    return {
        "title": title,
        "episode_number": episode_num,
        "audio_file": str(audio_path),
        "script_file": str(script_path),
        "duration": duration,
        "slug": slug,
    }
