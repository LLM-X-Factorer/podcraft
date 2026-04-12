"""Tests for script generation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from podcraft.script import _load_system_prompt, generate_script, _extract_list, _normalize_dialogue
from podcraft.config import PodcraftConfig, PodcastConfig, HostConfig, LLMConfig


@pytest.fixture
def en_config():
    return PodcraftConfig(
        podcast=PodcastConfig(language="en"),
        host=HostConfig(name="Alice"),
        guest=HostConfig(name="Bob"),
        llm=LLMConfig(engine="gemini"),
    )


@pytest.fixture
def zh_config():
    return PodcraftConfig(
        podcast=PodcastConfig(language="zh-cn"),
        host=HostConfig(name="小刘"),
        guest=HostConfig(name="美美"),
        llm=LLMConfig(engine="gemini"),
    )


def test_load_english_template(en_config):
    prompt = _load_system_prompt(en_config)
    assert "Alice" in prompt
    assert "Bob" in prompt
    assert "host" in prompt.lower()
    assert "guest" in prompt.lower()


def test_load_chinese_template(zh_config):
    prompt = _load_system_prompt(zh_config)
    assert "小刘" in prompt
    assert "美美" in prompt


def test_custom_prompt_template(en_config, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    custom = prompts_dir / "system.md"
    custom.write_text("You are a host named {{ host.name }} interviewing {{ guest.name }}.")
    en_config.paths["prompts"] = "prompts"

    prompt = _load_system_prompt(en_config, tmp_path)
    assert prompt == "You are a host named Alice interviewing Bob."


def test_template_includes_silence_duration(en_config):
    prompt = _load_system_prompt(en_config)
    assert "1.5" in prompt


@patch("podcraft.script.get_api_key", return_value="fake-key")
@patch("podcraft.script._generate_gemini")
def test_generate_script_calls_gemini(mock_gemini, mock_key, en_config):
    mock_gemini.return_value = [{"role": "host", "text": "Hello"}, {"role": "guest", "text": "Hi"}]
    result = generate_script("Some content", en_config)
    assert len(result) == 2
    assert result[0]["role"] == "host"
    mock_gemini.assert_called_once()


@patch("podcraft.script.get_api_key", return_value="fake-key")
@patch("podcraft.script._generate_anthropic")
def test_generate_script_calls_anthropic(mock_anthropic, mock_key):
    config = PodcraftConfig(llm=LLMConfig(engine="anthropic"))
    mock_anthropic.return_value = [{"role": "host", "text": "Hello"}]
    result = generate_script("Content", config)
    mock_anthropic.assert_called_once()


def test_auto_engine_no_key():
    config = PodcraftConfig(llm=LLMConfig(engine="auto"))
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="No API key found"):
            generate_script("Content", config)


# --- _extract_list tests ---

def test_extract_list_from_list():
    data = [{"role": "host", "text": "hi"}]
    assert _extract_list(data) == data


def test_extract_list_from_dict():
    data = {"dialogue": [{"role": "host", "text": "hi"}]}
    assert _extract_list(data) == [{"role": "host", "text": "hi"}]


def test_extract_list_from_nested_dict():
    data = {"result": {"meta": "ignored"}, "turns": [{"role": "guest", "text": "ok"}]}
    assert _extract_list(data) == [{"role": "guest", "text": "ok"}]


def test_extract_list_bad_type():
    with pytest.raises(ValueError, match="Expected list or dict"):
        _extract_list("not a list")


# --- _normalize_dialogue tests ---

def test_normalize_standard_format():
    raw = [{"role": "host", "text": "hi"}, {"role": "guest", "text": "hello"}]
    assert _normalize_dialogue(raw) == raw


def test_normalize_speaker_alias():
    raw = [{"speaker": "host", "text": "hi"}, {"speaker": "guest", "text": "hello"}]
    result = _normalize_dialogue(raw)
    assert result[0] == {"role": "host", "text": "hi"}
    assert result[1] == {"role": "guest", "text": "hello"}


def test_normalize_content_alias():
    raw = [{"role": "host", "content": "hi"}]
    result = _normalize_dialogue(raw)
    assert result[0] == {"role": "host", "text": "hi"}


def test_normalize_chinese_role_names():
    raw = [{"role": "主持人", "text": "hi"}, {"role": "专家", "text": "hello"}]
    result = _normalize_dialogue(raw)
    assert result[0]["role"] == "host"
    assert result[1]["role"] == "guest"


def test_normalize_missing_role_alternates():
    raw = [{"text": "first"}, {"text": "second"}, {"text": "third"}]
    result = _normalize_dialogue(raw)
    assert result[0]["role"] == "host"
    assert result[1]["role"] == "guest"
    assert result[2]["role"] == "host"


def test_normalize_skips_empty_text():
    raw = [{"role": "host", "text": ""}, {"role": "guest", "text": "ok"}]
    result = _normalize_dialogue(raw)
    assert len(result) == 1
    assert result[0]["role"] == "guest"


def test_normalize_skips_non_dict():
    raw = ["not a dict", {"role": "host", "text": "ok"}]
    result = _normalize_dialogue(raw)
    assert len(result) == 1


def test_normalize_empty_raises():
    with pytest.raises(ValueError, match="No valid dialogue turns"):
        _normalize_dialogue([])


def test_normalize_name_alias():
    raw = [{"name": "host", "text": "hi"}]
    result = _normalize_dialogue(raw)
    assert result[0]["role"] == "host"
