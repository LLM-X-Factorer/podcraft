"""Tests for CLI commands."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from podcraft.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_init_creates_files(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert Path("podcraft.yaml").exists()
        assert Path("prompts/system.md").exists()
        assert Path("output").is_dir()
        assert Path("scripts").is_dir()
        assert Path("episodes").is_dir()


def test_init_english_defaults(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(main, ["init", "--language", "en"])
        content = Path("podcraft.yaml").read_text()
        assert '"Alex"' in content
        assert '"Sam"' in content
        assert '"en"' in content


def test_init_chinese_defaults(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(main, ["init", "--language", "zh"])
        content = Path("podcraft.yaml").read_text()
        assert '"小刘"' in content
        assert '"美美"' in content
        assert '"zh"' in content


def test_init_refuses_if_exists(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("podcraft.yaml").write_text("existing")
        result = runner.invoke(main, ["init"])
        assert "already exists" in result.output


def test_init_custom_title(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(main, ["init", "--title", "Cool Podcast"])
        content = Path("podcraft.yaml").read_text()
        assert "Cool Podcast" in content


def test_publish_no_config(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["publish", "test.md"])
        assert result.exit_code != 0


def test_feed_no_config(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["feed"])
        assert result.exit_code != 0
