"""Research pipeline: web search → LLM synthesis → Markdown research document."""

import os
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, BaseLoader

from .config import PodcraftConfig, get_api_key

TEMPLATES_DIR = Path(__file__).parent / "templates"

# LLM preambles to strip
_PREAMBLES = re.compile(
    r"^(好的[，,。]?\s*|以下是\s*|当然[，,。]?\s*|Sure[,.]?\s*|Here(?:'s| is)[^:\n]*:\s*|Okay[,.]?\s*)",
    re.IGNORECASE,
)


def _load_prompt(config: PodcraftConfig, project_root: Path | None = None) -> str:
    """Load research prompt from user's prompts/ dir or built-in templates."""
    if project_root:
        custom_dir = project_root / config.paths.get("prompts", "prompts")
        custom_file = custom_dir / "research.md"
        if custom_file.exists():
            template_str = custom_file.read_text(encoding="utf-8")
            env = Environment(loader=BaseLoader())
            tpl = env.from_string(template_str)
            return tpl.render(config=config)

    lang = config.language[:2]
    template_name = f"research_{lang}.md" if (TEMPLATES_DIR / f"research_{lang}.md").exists() else "research_en.md"
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template(template_name)
    return tpl.render(config=config)


def _web_search(query: str, api_key: str, model: str = "gemini-2.5-flash") -> str:
    """Run a single web search using Gemini's Google Search grounding tool."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )
    return response.text.strip()


def research_topic(
    topic: str,
    config: PodcraftConfig,
    project_root: Path | None = None,
    search_queries: list[str] | None = None,
    description: str = "",
) -> str:
    """Research a topic via web search + LLM synthesis.

    Args:
        topic: The topic to research (used as fallback for search queries).
        config: PodcraftConfig with research settings.
        project_root: Used to find custom prompts/research.md.
        search_queries: Optional custom search queries. If None, uses topic-based defaults.
        description: Optional topic description for more targeted queries.

    Returns:
        Markdown-formatted research document string.
    """
    if not config.research.enabled:
        raise RuntimeError(
            "Research is disabled. Set research.enabled: true in podcraft.yaml."
        )

    api_key = get_api_key("gemini")
    model = config.llm.model or "gemini-2.5-flash"
    max_chars = config.research.max_research_chars
    max_searches = config.research.max_searches

    # Build default search queries from topic if not provided
    if not search_queries:
        search_queries = _default_queries(topic, description, config)

    # Run web searches
    search_results = []
    for i, query in enumerate(search_queries[:max_searches]):
        print(f"  Searching ({i + 1}/{min(len(search_queries), max_searches)}): {query}")
        try:
            result = _web_search(query, api_key, model)
            search_results.append(f"### 搜索：{query}\n\n{result}")
        except Exception as e:
            print(f"  Search failed: {e}")

    if not search_results:
        raise RuntimeError(f"All web searches failed for topic: {topic!r}")

    # Combine results (cap at max_chars)
    combined = "\n\n---\n\n".join(search_results)
    if len(combined) > max_chars:
        combined = combined[:max_chars]

    # Synthesize with LLM
    system_prompt = _load_prompt(config, project_root)
    topic_line = f"Topic: {topic}"
    if description:
        topic_line += f"\nDescription: {description}"
    user_prompt = f"{topic_line}\n\n## Web Research Results\n\n{combined}"

    print(f"  Synthesizing research ({len(combined)} chars of search results)...")
    result = _synthesize(system_prompt, user_prompt, api_key, model, config)

    # Strip preambles
    result = _PREAMBLES.sub("", result.strip()).strip()
    return result


def _default_queries(topic: str, description: str, config: PodcraftConfig) -> list[str]:
    """Build default search queries from topic."""
    lang = config.language[:2]
    if lang == "zh":
        queries = [
            f"{topic} 介绍 案例分析",
            f"{topic} 历史 发展 影响",
            f"{topic} 技巧 实践 应用",
        ]
    elif lang == "ja":
        queries = [
            f"{topic} 解説 事例",
            f"{topic} 歴史 発展",
            f"{topic} 活用 実践",
        ]
    else:
        queries = [
            f"{topic} introduction examples",
            f"{topic} history development",
            f"{topic} practical applications techniques",
        ]
    return queries


def _synthesize(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    config: PodcraftConfig,
) -> str:
    """Call Gemini to synthesize research from web search results."""
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": config.research.temperature,
            "max_output_tokens": config.research.max_output_tokens,
        },
    )
    return response.text.strip()
