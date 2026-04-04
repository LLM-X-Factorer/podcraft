"""Show notes generation from podcast dialogue via LLM."""

import os
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, BaseLoader

from .config import PodcraftConfig, get_api_key

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Individual preamble patterns to strip iteratively from the start of LLM output.
# Only strip fixed-length intro phrases, not the actual content that follows.
_PREAMBLE_PARTS = re.compile(
    r"^(好的[，,。]?\s*|以下是\s*|当然[，,。]?\s*|Sure[,.]?\s*|Here(?:'s| is)\s*(?:are\s*)?(?:the\s*)?(?:show\s*notes?)?[:\s]*|Okay[,.]?\s*|Of course[,.]?\s*)",
    re.IGNORECASE,
)


def _strip_preambles(text: str) -> str:
    """Strip LLM preamble phrases from the start of text (handles chained preambles)."""
    prev = None
    while prev != text:
        prev = text
        text = _PREAMBLE_PARTS.sub("", text)
    return text.strip()


def _load_prompt(config: PodcraftConfig, project_root: Path | None = None) -> str:
    """Load show notes prompt from user's prompts/ dir or built-in templates."""
    if project_root:
        custom_dir = project_root / config.paths.get("prompts", "prompts")
        custom_file = custom_dir / "shownotes.md"
        if custom_file.exists():
            template_str = custom_file.read_text(encoding="utf-8")
            env = Environment(loader=BaseLoader())
            tpl = env.from_string(template_str)
            return tpl.render(host=config.host, guest=config.guest, config=config)

    lang = config.language[:2]
    template_name = f"shownotes_{lang}.md" if (TEMPLATES_DIR / f"shownotes_{lang}.md").exists() else "shownotes_en.md"
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template(template_name)
    return tpl.render(host=config.host, guest=config.guest, config=config)


def generate_show_notes(
    dialogue: list[dict],
    config: PodcraftConfig,
    project_root: Path | None = None,
    title: str = "",
) -> str:
    """Generate plain-text show notes from podcast dialogue using LLM."""
    if not config.shownotes.enabled:
        return ""

    # Build dialogue sample (max 6000 chars)
    host_name = config.host.name
    guest_name = config.guest.name
    lines = []
    for turn in dialogue:
        name = host_name if turn["role"] == "host" else guest_name
        lines.append(f"{name}：{turn['text']}")
    dialogue_text = "\n".join(lines)[:6000]

    system_prompt = _load_prompt(config, project_root)
    title_line = f"本期标题：{title}\n\n" if title else ""
    user_prompt = f"{title_line}以下是本期播客对话：\n\n{dialogue_text}"

    engine = config.llm.engine
    if engine == "auto":
        for name, env_var in [("gemini", "GEMINI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")]:
            if os.environ.get(env_var):
                engine = name
                break
        else:
            return ""

    try:
        if engine == "gemini":
            result = _generate_gemini(system_prompt, user_prompt, config)
        elif engine == "anthropic":
            result = _generate_anthropic(system_prompt, user_prompt, config)
        elif engine == "openai":
            result = _generate_openai(system_prompt, user_prompt, config)
        else:
            return ""
    except Exception as e:
        print(f"  Show notes generation failed: {e}")
        return ""

    return _strip_preambles(result)


def _generate_gemini(system_prompt: str, user_prompt: str, config: PodcraftConfig) -> str:
    from google import genai

    client = genai.Client(api_key=get_api_key("gemini"))
    response = client.models.generate_content(
        model=config.llm.model or "gemini-2.5-flash",
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": config.shownotes.temperature,
            "max_output_tokens": config.shownotes.max_tokens,
        },
    )
    return response.text.strip()


def _generate_anthropic(system_prompt: str, user_prompt: str, config: PodcraftConfig) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key("anthropic"))
    response = client.messages.create(
        model=config.llm.model or "claude-sonnet-4-20250514",
        max_tokens=config.shownotes.max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


def _generate_openai(system_prompt: str, user_prompt: str, config: PodcraftConfig) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=get_api_key("openai"))
    response = client.chat.completions.create(
        model=config.llm.model or "gpt-4o",
        temperature=config.shownotes.temperature,
        max_tokens=config.shownotes.max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
