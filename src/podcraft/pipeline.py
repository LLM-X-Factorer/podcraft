"""Core pipeline: document → script → audio → cover → show notes → release → RSS."""

import asyncio
import json
import subprocess
from datetime import datetime, timezone, timedelta
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
    """Full pipeline: document → script → audio → cover → show notes → release → RSS.

    Steps 4-7 are skipped when the relevant config is disabled.
    Returns episode metadata dict.
    """
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
    total_steps = _count_steps(config)
    print(f"\n{'=' * 60}")
    print(f"Publishing: {title}")
    print(f"  Source: {input_path}")
    print(f"  Episode: #{episode_num}  Steps: {total_steps}")
    print(f"{'=' * 60}")

    step = 0

    # Step 1: Read document
    step += 1
    print(f"\n[{step}/{total_steps}] Reading document...")
    content = read_document(input_path)
    if len(content) > 120000:
        print(f"  Truncating from {len(content)} to 120000 chars")
        content = content[:120000]
    print(f"  {len(content)} chars loaded")

    # Step 2: Generate script
    step += 1
    script_path = scripts_dir / f"{slug}_script.json"
    if script_path.exists():
        print(f"\n[{step}/{total_steps}] Loading existing script: {script_path}")
        dialogue = json.loads(script_path.read_text(encoding="utf-8"))
    else:
        print(f"\n[{step}/{total_steps}] Generating podcast script...")
        dialogue = generate_script(content, config, project_root, focus)
        script_path.write_text(
            json.dumps(dialogue, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        readable_path = script_path.with_suffix(".txt")
        lines = []
        for turn in dialogue:
            name = config.host.name if turn["role"] == "host" else config.guest.name
            lines.append(f"[{name}] {turn['text']}\n")
        readable_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {len(dialogue)} dialogue turns")

    # Step 3: Synthesize audio
    step += 1
    audio_path = output_dir / f"{slug}.mp3"
    if audio_path.exists():
        print(f"\n[{step}/{total_steps}] Audio already exists: {audio_path}")
    else:
        print(f"\n[{step}/{total_steps}] Synthesizing audio ({config.tts.engine})...")
        engine = create_engine(config)
        asyncio.run(engine.synthesize_dialogue(dialogue, str(audio_path)))

    duration = get_duration(audio_path)
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    size_mb = audio_path.stat().st_size / 1024 / 1024
    print(f"  Duration: {minutes}:{seconds:02d}, Size: {size_mb:.1f} MB")

    # Step 4: Generate cover (optional)
    cover_file = None
    if config.cover.engine != "disabled":
        step += 1
        from .cover import create_cover_engine
        cover_path = output_dir / f"{slug}_cover.png"
        print(f"\n[{step}/{total_steps}] Generating cover ({config.cover.engine})...")
        cover_engine = create_cover_engine(config)
        if cover_engine:
            try:
                cover_engine.generate(title, episode_num, cover_path)
                cover_file = str(cover_path)
            except Exception as e:
                print(f"  Cover generation failed: {e}")

    # Step 5: Generate show notes (optional)
    show_notes = None
    if config.shownotes.enabled:
        step += 1
        notes_path = scripts_dir / f"{slug}_notes.txt"
        if notes_path.exists():
            print(f"\n[{step}/{total_steps}] Loading existing show notes")
            show_notes = notes_path.read_text(encoding="utf-8")
        else:
            print(f"\n[{step}/{total_steps}] Generating show notes...")
            from .shownotes import generate_show_notes
            show_notes = generate_show_notes(dialogue, config, project_root, title)
            if show_notes:
                notes_path.write_text(show_notes, encoding="utf-8")
                print(f"  Show notes saved: {notes_path}")

    # Step 6: Upload to GitHub Release (optional)
    audio_url = None
    if config.release.enabled:
        step += 1
        print(f"\n[{step}/{total_steps}] Uploading to GitHub Release ({config.release.tag})...")
        from .release import upload_to_release
        upload_files = [audio_path]
        if cover_file:
            upload_files.append(Path(cover_file))
        try:
            urls = upload_to_release(
                upload_files,
                repo=config.release.repo,
                tag=config.release.tag,
            )
            audio_url = next((u for u in urls if u.endswith(".mp3")), None)
            print(f"  Uploaded {len(urls)} files")
        except Exception as e:
            print(f"  Release upload failed: {e}")

    # Step 7: Update RSS feed + git push (optional)
    if config.release.enabled and audio_url:
        step += 1
        print(f"\n[{step}/{total_steps}] Updating RSS feed...")
        try:
            _update_rss_and_push(config, project_root, paths)
        except Exception as e:
            print(f"  RSS update failed: {e}")

    print(f"\n{'=' * 60}")
    print(f"Done: {title}")
    print(f"  Audio:  {audio_path}")
    print(f"  Script: {script_path}")
    if cover_file:
        print(f"  Cover:  {cover_file}")
    if show_notes:
        print(f"  Notes:  {scripts_dir / (slug + '_notes.txt')}")
    if audio_url:
        print(f"  URL:    {audio_url}")
    print(f"{'=' * 60}")

    return {
        "title": title,
        "episode_number": episode_num,
        "audio_file": str(audio_path),
        "script_file": str(script_path),
        "duration": duration,
        "slug": slug,
        "cover_file": cover_file,
        "show_notes": show_notes,
        "audio_url": audio_url,
    }


def _count_steps(config: PodcraftConfig) -> int:
    """Count active pipeline steps based on config."""
    steps = 3  # read, script, audio
    if config.cover.engine != "disabled":
        steps += 1
    if config.shownotes.enabled:
        steps += 1
    if config.release.enabled:
        steps += 1  # upload
        steps += 1  # RSS
    return steps


def _update_rss_and_push(config: PodcraftConfig, project_root: Path, paths: dict) -> None:
    """Regenerate RSS feed, git commit, and push."""
    from .feed import build_rss
    from datetime import datetime, timezone, timedelta

    output_dir = paths["output"]
    scripts_dir = paths["scripts"]

    mp3_files = sorted(
        f for f in output_dir.glob("*.mp3")
        if "silence" not in f.name and "test" not in f.name
    )

    tz = timezone(timedelta(hours=8))
    ep_list = []
    for i, ep_path in enumerate(mp3_files):
        notes_path = scripts_dir / f"{ep_path.stem}_notes.txt"
        description = (
            notes_path.read_text(encoding="utf-8")
            if notes_path.exists()
            else f"{config.podcast.title} - {ep_path.stem}"
        )
        audio_url = f"{config.feed.audio_base_url}/{ep_path.name}" if config.feed.audio_base_url else ""
        ep_list.append({
            "title": f"EP{i + 1:02d}: {ep_path.stem.replace('-', ' ').replace('_', ' ').title()}",
            "description": description,
            "audio_file": str(ep_path),
            "audio_url": audio_url,
            "pub_date": datetime.now(tz) - timedelta(days=len(mp3_files) - i - 1),
            "episode_number": i + 1,
        })

    rss_xml = build_rss(ep_list, config)
    feed_path = project_root / config.feed.output
    feed_path.write_text(rss_xml, encoding="utf-8")
    print(f"  RSS updated: {len(ep_list)} episodes → {feed_path}")

    # Git commit and push
    try:
        subprocess.run(["git", "add", str(feed_path)], cwd=project_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Update RSS feed ({len(ep_list)} episodes)"],
            cwd=project_root, check=True,
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=project_root, check=True)
        print("  Git pushed")
    except subprocess.CalledProcessError as e:
        print(f"  Git push failed: {e}")
