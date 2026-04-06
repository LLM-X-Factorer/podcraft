"""Episode manifest: persistent metadata for published episodes."""

import json
from datetime import datetime
from pathlib import Path

MANIFEST_FILENAME = "episodes.json"


def load_manifest(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        return []
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def save_manifest(manifest_path: Path, episodes: list[dict]) -> None:
    episodes.sort(key=lambda e: e.get("episode_number", 0))
    manifest_path.write_text(
        json.dumps(episodes, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def add_episode(manifest_path: Path, episode: dict) -> None:
    """Add or update an episode in the manifest (keyed by episode_number)."""
    episodes = load_manifest(manifest_path)
    ep_num = episode["episode_number"]

    # Replace if same episode_number exists
    episodes = [e for e in episodes if e.get("episode_number") != ep_num]
    episodes.append(episode)
    save_manifest(manifest_path, episodes)


def build_manifest_entry(
    title: str,
    episode_number: int,
    audio_file: str,
    audio_url: str,
    description: str,
    pub_date: datetime,
    cover_file: str | None = None,
) -> dict:
    """Create a standardized manifest entry."""
    return {
        "title": title,
        "episode_number": episode_number,
        "audio_file": audio_file,
        "audio_url": audio_url or "",
        "description": description,
        "pub_date": pub_date.isoformat(),
        "cover_file": cover_file or "",
    }
