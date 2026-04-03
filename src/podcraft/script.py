"""Markdown → dialogue script generation via LLM."""

import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, BaseLoader

from .config import PodcraftConfig, get_api_key

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_system_prompt(config: PodcraftConfig, project_root: Path | None = None) -> str:
    """Load system prompt from user's prompts/ dir or built-in templates."""
    # Check user's custom prompts directory first
    if project_root:
        custom_dir = project_root / config.paths.get("prompts", "prompts")
        custom_file = custom_dir / "system.md"
        if custom_file.exists():
            template_str = custom_file.read_text(encoding="utf-8")
            env = Environment(loader=BaseLoader())
            tpl = env.from_string(template_str)
            return tpl.render(host=config.host, guest=config.guest, config=config)

    # Built-in templates
    lang = config.language[:2]
    template_name = f"system_{lang}.md" if (TEMPLATES_DIR / f"system_{lang}.md").exists() else "system_en.md"
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template(template_name)
    return tpl.render(host=config.host, guest=config.guest, config=config)


def generate_script(
    content: str,
    config: PodcraftConfig,
    project_root: Path | None = None,
    focus: str = "",
) -> list[dict]:
    """Generate podcast dialogue script from document content."""
    engine = config.llm.engine

    # Auto-detect engine from available keys
    if engine == "auto":
        for name, env_var in [("gemini", "GEMINI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")]:
            if os.environ.get(env_var):
                engine = name
                break
        else:
            raise RuntimeError("No API key found. Set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")

    system_prompt = _load_system_prompt(config, project_root)

    lang_hint = "中文" if config.language.startswith("zh") else config.language
    user_prompt = f"请将以下文档转换为播客对话脚本（使用{lang_hint}）：\n\n{content}"
    if focus:
        user_prompt += f"\n\n重点关注以下方面：{focus}"

    if engine == "gemini":
        return _generate_gemini(system_prompt, user_prompt, config)
    elif engine == "anthropic":
        return _generate_anthropic(system_prompt, user_prompt, config)
    elif engine == "openai":
        return _generate_openai(system_prompt, user_prompt, config)
    else:
        raise ValueError(f"Unknown LLM engine: {engine}")


def _generate_gemini(system_prompt: str, user_prompt: str, config: PodcraftConfig) -> list[dict]:
    from google import genai

    client = genai.Client(api_key=get_api_key("gemini"))

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=config.llm.model or "gemini-2.5-flash",
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": config.llm.temperature,
                    "max_output_tokens": config.llm.max_output_tokens,
                    "response_mime_type": "application/json",
                },
            )
            return json.loads(response.text.strip())
        except (json.JSONDecodeError, Exception) as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise


def _generate_anthropic(system_prompt: str, user_prompt: str, config: PodcraftConfig) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key("anthropic"))
    response = client.messages.create(
        model=config.llm.model or "claude-sonnet-4-20250514",
        max_tokens=config.llm.max_output_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def _generate_openai(system_prompt: str, user_prompt: str, config: PodcraftConfig) -> list[dict]:
    from openai import OpenAI

    client = OpenAI(api_key=get_api_key("openai"))
    response = client.chat.completions.create(
        model=config.llm.model or "gpt-4o",
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_output_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    data = json.loads(response.choices[0].message.content)
    # OpenAI json_object wraps in a key; extract the array
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    return data
