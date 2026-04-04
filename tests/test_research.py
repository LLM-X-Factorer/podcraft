"""Tests for research pipeline."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from podcraft.config import PodcraftConfig, PodcastConfig, LLMConfig, ResearchConfig
from podcraft.research import research_topic, _default_queries, _load_prompt


@pytest.fixture
def research_config():
    return PodcraftConfig(
        podcast=PodcastConfig(title="Test Podcast", language="en"),
        llm=LLMConfig(engine="gemini"),
        research=ResearchConfig(enabled=True, max_searches=2, max_research_chars=5000),
    )


def test_research_disabled_raises(research_config):
    research_config.research.enabled = False
    with pytest.raises(RuntimeError, match="Research is disabled"):
        research_topic("test topic", research_config)


def test_default_queries_english(research_config):
    queries = _default_queries("Typography", "", research_config)
    assert len(queries) == 3
    assert all("Typography" in q for q in queries)


def test_default_queries_chinese():
    config = PodcraftConfig(
        podcast=PodcastConfig(language="zh"),
        research=ResearchConfig(enabled=True),
    )
    queries = _default_queries("字体排印", "", config)
    assert len(queries) == 3
    assert all("字体排印" in q for q in queries)


def test_research_config_defaults():
    config = PodcraftConfig()
    assert config.research.enabled is False
    assert config.research.search_engine == "gemini_grounding"
    assert config.research.max_searches == 3
    assert config.research.max_research_chars == 30000
    assert config.research.max_output_tokens == 8192


def test_research_config_from_yaml(tmp_path):
    from podcraft.config import load_config
    yaml_content = """
podcast:
  title: "Test"
research:
  enabled: true
  max_searches: 5
  max_research_chars: 20000
  temperature: 0.5
"""
    config_path = tmp_path / "podcraft.yaml"
    config_path.write_text(yaml_content)
    config, root = load_config(config_path)
    assert config.research.enabled is True
    assert config.research.max_searches == 5
    assert config.research.max_research_chars == 20000
    assert config.research.temperature == 0.5


def test_load_prompt_builtin_en(research_config):
    prompt = _load_prompt(research_config)
    assert "research" in prompt.lower() or "podcast" in prompt.lower()


def test_custom_research_prompt(research_config, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "research.md").write_text("Custom research prompt for {{ config.podcast.title }}")
    research_config.paths["prompts"] = "prompts"
    prompt = _load_prompt(research_config, tmp_path)
    assert "Test Podcast" in prompt


def test_custom_search_queries(research_config):
    """Custom queries override default ones."""
    with patch("podcraft.research.get_api_key", return_value="fake"), \
         patch("podcraft.research._web_search", return_value="search result") as mock_search, \
         patch("podcraft.research._synthesize", return_value="# Research\n\nContent"):
        result = research_topic(
            "Typography",
            research_config,
            search_queries=["query one", "query two"],
        )
    assert mock_search.call_count == 2
    calls = [c[0][0] for c in mock_search.call_args_list]
    assert "query one" in calls
    assert "query two" in calls


@pytest.mark.integration
def test_research_topic_integration(research_config):
    pytest.importorskip("google.genai")
    import os
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    result = research_topic("Typography basics", research_config)
    assert isinstance(result, str)
    assert len(result) > 200
    assert result.startswith("#")
