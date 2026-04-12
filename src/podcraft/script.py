"""Markdown → dialogue script generation via LLM."""

import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, BaseLoader

from .config import PodcraftConfig, get_api_key

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Maps common alternative field names to the canonical "role"/"text" keys
_ROLE_ALIASES = {"speaker", "character", "name", "actor"}
_TEXT_ALIASES = {"content", "dialogue", "line", "message", "speech"}


def _extract_list(data) -> list:
    """Extract dialogue list from LLM output that may be wrapped in a dict."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    raise ValueError(f"Expected list or dict wrapping a list, got {type(data).__name__}")


def _normalize_dialogue(raw: list) -> list[dict]:
    """Validate and normalize dialogue turns to [{"role": ..., "text": ...}, ...]."""
    result = []
    for i, turn in enumerate(raw):
        if not isinstance(turn, dict):
            continue

        # Resolve role
        role = turn.get("role")
        if role is None:
            for alias in _ROLE_ALIASES:
                if alias in turn:
                    role = turn[alias]
                    break
        if role is None:
            # Alternate between host/guest based on position
            role = "host" if len(result) % 2 == 0 else "guest"

        # Normalize role value
        role = str(role).lower().strip()
        if role not in ("host", "guest"):
            # Try to infer from common patterns
            if any(k in role for k in ("主持", "host", "主播")):
                role = "host"
            else:
                role = "guest"

        # Resolve text
        text = turn.get("text")
        if text is None:
            for alias in _TEXT_ALIASES:
                if alias in turn:
                    text = turn[alias]
                    break
        if not text:
            continue

        result.append({"role": role, "text": str(text)})

    if not result:
        raise ValueError("No valid dialogue turns found in LLM output")

    return result


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
        raw = _generate_gemini(system_prompt, user_prompt, config)
    elif engine == "anthropic":
        raw = _generate_anthropic(system_prompt, user_prompt, config)
    elif engine == "openai":
        raw = _generate_openai(system_prompt, user_prompt, config)
    else:
        raise ValueError(f"Unknown LLM engine: {engine}")

    return _normalize_dialogue(_extract_list(raw))


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
            data = json.loads(response.text.strip())
            return _extract_list(data)
        except (json.JSONDecodeError, ValueError, Exception) as e:
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
    return _extract_list(data)
