"""GitHub Release management via gh CLI."""

import subprocess
from pathlib import Path


def _detect_repo() -> str:
    """Auto-detect GitHub repo from git remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
        url = result.stdout.strip()
        # SSH: git@github.com:owner/repo.git
        # HTTPS: https://github.com/owner/repo.git
        if "github.com" in url:
            url = url.replace("git@github.com:", "").replace("https://github.com/", "")
            return url.removesuffix(".git")
    except Exception:
        pass
    return ""


def create_release_if_needed(repo: str, tag: str) -> None:
    """Create a GitHub Release for the given tag if it doesn't exist."""
    if not repo:
        repo = _detect_repo()
    if not repo:
        raise RuntimeError("Cannot determine GitHub repo. Set release.repo in podcraft.yaml.")

    # Check if release exists
    result = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return  # Already exists

    subprocess.run(
        ["gh", "release", "create", tag, "--repo", repo,
         "--title", tag, "--notes", "Podcast audio files"],
        check=True,
    )


def upload_to_release(
    files: list[Path],
    repo: str = "",
    tag: str = "v1.0.0-podcast",
    clobber: bool = True,
) -> list[str]:
    """Upload files to a GitHub Release. Returns list of asset URLs."""
    if not repo:
        repo = _detect_repo()
    if not repo:
        raise RuntimeError("Cannot determine GitHub repo. Set release.repo in podcraft.yaml.")

    create_release_if_needed(repo, tag)

    cmd = ["gh", "release", "upload", tag, "--repo", repo]
    if clobber:
        cmd.append("--clobber")
    cmd.extend(str(f) for f in files)

    subprocess.run(cmd, check=True)

    # Build asset URLs (GitHub raw download pattern)
    base = f"https://github.com/{repo}/releases/download/{tag}"
    return [f"{base}/{Path(f).name}" for f in files]
