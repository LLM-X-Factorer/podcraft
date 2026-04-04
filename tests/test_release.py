"""Tests for GitHub Release upload."""

import pytest
from unittest.mock import patch, call
from pathlib import Path

from podcraft.config import PodcraftConfig, ReleaseConfig
from podcraft.release import upload_to_release, create_release_if_needed, _detect_repo


def test_release_config_defaults():
    config = PodcraftConfig()
    assert config.release.enabled is False
    assert config.release.repo == ""
    assert config.release.tag == "v1.0.0-podcast"


def test_release_config_from_yaml(tmp_path):
    from podcraft.config import load_config
    yaml_content = """
podcast:
  title: "My Pod"
release:
  enabled: true
  repo: "owner/my-podcast"
  tag: "v2.0.0-audio"
"""
    config_path = tmp_path / "podcraft.yaml"
    config_path.write_text(yaml_content)
    config, root = load_config(config_path)
    assert config.release.enabled is True
    assert config.release.repo == "owner/my-podcast"
    assert config.release.tag == "v2.0.0-audio"


def test_upload_builds_correct_urls(tmp_path):
    audio = tmp_path / "ep01.mp3"
    audio.write_bytes(b"fake audio")

    with patch("podcraft.release.create_release_if_needed"), \
         patch("podcraft.release.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        urls = upload_to_release([audio], repo="owner/repo", tag="v1.0.0-podcast")

    assert urls == ["https://github.com/owner/repo/releases/download/v1.0.0-podcast/ep01.mp3"]


def test_upload_raises_without_repo(tmp_path):
    audio = tmp_path / "ep01.mp3"
    audio.write_bytes(b"fake audio")

    with patch("podcraft.release._detect_repo", return_value=""):
        with pytest.raises(RuntimeError, match="Cannot determine GitHub repo"):
            upload_to_release([audio], repo="")


def test_create_release_skips_if_exists():
    with patch("podcraft.release.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0  # release exists
        create_release_if_needed("owner/repo", "v1.0.0")
        # Only one call: gh release view
        assert mock_run.call_count == 1


def test_create_release_creates_if_missing():
    results = [MagicMock(returncode=1), MagicMock(returncode=0)]

    with patch("podcraft.release.subprocess.run", side_effect=results):
        create_release_if_needed("owner/repo", "v1.0.0")


def test_detect_repo_from_ssh_remote():
    with patch("podcraft.release.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "git@github.com:owner/my-repo.git\n"
        repo = _detect_repo()
    assert repo == "owner/my-repo"


def test_detect_repo_from_https_remote():
    with patch("podcraft.release.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "https://github.com/owner/my-repo.git\n"
        repo = _detect_repo()
    assert repo == "owner/my-repo"


def test_detect_repo_returns_empty_on_failure():
    with patch("podcraft.release.subprocess.run", side_effect=Exception("git error")):
        repo = _detect_repo()
    assert repo == ""


# Fix missing import in test_create_release_creates_if_missing
from unittest.mock import MagicMock
