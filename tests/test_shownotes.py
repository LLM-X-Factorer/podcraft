"""Tests for show notes generation."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from podcraft.config import PodcraftConfig, PodcastConfig, ShowNotesConfig, HostConfig, LLMConfig
from podcraft.shownotes import generate_show_notes, _strip_preambles


@pytest.fixture
def notes_config():
    return PodcraftConfig(
        podcast=PodcastConfig(title="Test Podcast", language="en"),
        host=HostConfig(name="Alice"),
        guest=HostConfig(name="Bob"),
        llm=LLMConfig(engine="gemini"),
        shownotes=ShowNotesConfig(enabled=True, max_tokens=500),
    )


@pytest.fixture
def dialogue():
    return [
        {"role": "host", "text": "What is the Pomodoro Technique?"},
        {"role": "guest", "text": "It's a time management method using 25-minute intervals."},
        {"role": "host", "text": "Does it really work?"},
        {"role": "guest", "text": "Yes, it helps maintain focus through timeboxing."},
    ]


def test_disabled_returns_empty(notes_config, dialogue):
    notes_config.shownotes.enabled = False
    result = generate_show_notes(dialogue, notes_config)
    assert result == ""


def test_preamble_stripping():
    assert _strip_preambles("好的，以下是节目介绍") == "节目介绍"
    assert _strip_preambles("好的，节目介绍开始") == "节目介绍开始"
    assert _strip_preambles("Sure, here are the show notes") == "here are the show notes"
    assert _strip_preambles("以下是本期内容") == "本期内容"
    assert _strip_preambles("正文内容") == "正文内容"
    assert _strip_preambles("当然，这是本期介绍") == "这是本期介绍"


@pytest.mark.integration
def test_generate_with_gemini(notes_config, dialogue):
    pytest.importorskip("google.genai")
    import os
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    result = generate_show_notes(dialogue, notes_config, title="EP01: Pomodoro")
    assert isinstance(result, str)
    assert len(result) > 50


def test_generate_gemini_mocked(notes_config, dialogue):
    mock_response = MagicMock()
    mock_response.text = "A great episode about time management.\n\nHighlights\n● Focus\n● Breaks"

    with patch("podcraft.shownotes.get_api_key", return_value="fake"), \
         patch("podcraft.shownotes._generate_gemini", return_value="A great episode about time management.\n\nHighlights\n● Focus\n● Breaks"):
        result = generate_show_notes(dialogue, notes_config, title="EP01: Test")

    assert "great episode" in result
    assert "Highlights" in result


def test_generate_returns_empty_on_error(notes_config, dialogue):
    with patch("podcraft.shownotes.get_api_key", side_effect=RuntimeError("no key")):
        result = generate_show_notes(dialogue, notes_config)
    assert result == ""


def test_shownotes_config_defaults():
    config = PodcraftConfig()
    assert config.shownotes.enabled is True
    assert config.shownotes.max_tokens == 1500
    assert config.shownotes.temperature == 0.5


def test_shownotes_config_from_yaml(tmp_path):
    from podcraft.config import load_config
    yaml_content = """
podcast:
  title: "My Pod"
  language: "en"
shownotes:
  enabled: false
  max_tokens: 800
  temperature: 0.3
"""
    config_path = tmp_path / "podcraft.yaml"
    config_path.write_text(yaml_content)
    config, root = load_config(config_path)
    assert config.shownotes.enabled is False
    assert config.shownotes.max_tokens == 800
    assert config.shownotes.temperature == 0.3


def test_custom_prompt_template(notes_config, dialogue, tmp_path):
    """Custom prompts/shownotes.md should be used when present."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "shownotes.md").write_text(
        "Write a one-sentence summary. Host: {{ host.name }}, Guest: {{ guest.name }}"
    )
    # Verify the prompt loads without error (just check _load_prompt)
    from podcraft.shownotes import _load_prompt
    notes_config.paths["prompts"] = "prompts"
    prompt = _load_prompt(notes_config, tmp_path)
    assert "Alice" in prompt
    assert "Bob" in prompt
