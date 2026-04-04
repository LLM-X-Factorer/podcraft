"""Cover image generation: pluggable factory supporting multiple engines."""

import os
import re
from pathlib import Path

from jinja2 import Environment, BaseLoader

from .config import PodcraftConfig

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Default overlay config
_OVERLAY_DEFAULTS = {
    "title_font_size": 80,
    "subtitle_font_size": 28,
    "episode_font_size": 32,
    "title_color": [212, 175, 105],
    "subtitle_color": [180, 155, 100],
    "episode_color": [200, 200, 200],
    "padding": 60,
}


def create_cover_engine(config: PodcraftConfig):
    """Factory: return the appropriate cover engine based on config."""
    engine_name = config.cover.engine
    if engine_name == "disabled":
        return None
    elif engine_name == "placeholder":
        return PlaceholderCoverEngine(config)
    elif engine_name == "imagen":
        return ImagenCoverEngine(config)
    else:
        raise ValueError(f"Unknown cover engine: {engine_name!r}. Use: disabled, placeholder, imagen")


class PlaceholderCoverEngine:
    """Generate a simple solid-color cover with text overlay. No external APIs required."""

    def __init__(self, config: PodcraftConfig):
        self.config = config

    def generate(self, title: str, episode_num: int, output_path: str | Path) -> Path:
        """Generate a placeholder cover with podcast title and episode number."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise ImportError("Pillow is required for cover generation: pip install podcraft[imagen]")

        cfg = self.config.cover
        overlay = {**_OVERLAY_DEFAULTS, **cfg.overlay}
        size = cfg.size

        # Background: dark gradient-ish solid color
        bg_color = tuple(overlay.get("bg_color", [20, 20, 30]))
        img = Image.new("RGB", (size, size), bg_color)
        draw = ImageDraw.Draw(img)

        podcast_title = overlay.get("title") or self.config.podcast.title
        subtitle = overlay.get("subtitle") or ""

        title_color = tuple(overlay["title_color"])
        subtitle_color = tuple(overlay["subtitle_color"])
        episode_color = tuple(overlay["episode_color"])
        pad = overlay["padding"]

        # Try to load a font, fall back to default
        def _get_font(size_pt: int):
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            ]
            for fp in font_paths:
                if Path(fp).exists():
                    try:
                        return ImageFont.truetype(fp, size_pt)
                    except Exception:
                        continue
            return ImageFont.load_default()

        ep_font = _get_font(overlay["episode_font_size"])
        title_font = _get_font(overlay["title_font_size"])
        sub_font = _get_font(overlay["subtitle_font_size"])

        # Draw episode number top-left
        draw.text((pad, pad), f"EP{episode_num:02d}", font=ep_font, fill=episode_color)

        # Draw podcast title bottom-left
        draw.text((pad, size - pad - overlay["title_font_size"] - overlay["subtitle_font_size"] - 20),
                  podcast_title, font=title_font, fill=title_color)

        # Draw subtitle below title
        if subtitle:
            draw.text((pad, size - pad - overlay["subtitle_font_size"]),
                      subtitle, font=sub_font, fill=subtitle_color)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))
        return output_path


class ImagenCoverEngine:
    """Generate cover art using Google Gemini Imagen 4 with PIL text overlay."""

    def __init__(self, config: PodcraftConfig):
        self.config = config
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set. Required for imagen cover engine.")

    def _build_prompt(self, title: str, episode_num: int) -> str:
        """Build the Imagen prompt, with optional theme_keywords mapping."""
        cfg = self.config.cover

        # Custom Jinja2 template from config
        if cfg.prompt_template:
            env = Environment(loader=BaseLoader())
            tpl = env.from_string(cfg.prompt_template)
            return tpl.render(
                title=title,
                episode_num=episode_num,
                config=self.config,
            )

        # Try to match theme keywords
        if cfg.theme_keywords:
            title_lower = title.lower()
            for keyword, prompt in cfg.theme_keywords.items():
                if keyword.lower() in title_lower:
                    return prompt

        # Built-in template per language
        lang = self.config.language[:2]
        template_file = TEMPLATES_DIR / f"cover_prompt_{lang}.md"
        if not template_file.exists():
            template_file = TEMPLATES_DIR / "cover_prompt_en.md"
        if template_file.exists():
            template_str = template_file.read_text(encoding="utf-8")
            env = Environment(loader=BaseLoader())
            tpl = env.from_string(template_str)
            return tpl.render(title=title, episode_num=episode_num, config=self.config)

        # Minimal fallback
        return (
            f"Abstract podcast cover art. Topic: {title}. "
            "Artistic, high quality, no text, no letters, no words. 1:1 square format."
        )

    def generate(self, title: str, episode_num: int, output_path: str | Path) -> Path:
        """Generate cover using Imagen 4, with PIL text overlay on top."""
        try:
            from google import genai
            from google.genai import types
            from PIL import Image, ImageDraw, ImageFont
            import io
        except ImportError:
            raise ImportError(
                "google-genai and Pillow are required: pip install podcraft[imagen]"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cfg = self.config.cover
        api_key = os.environ.get("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)
        prompt = self._build_prompt(title, episode_num)

        img = None

        # Try Imagen 4 first
        try:
            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1",
                ),
            )
            if response.generated_images:
                raw = response.generated_images[0].image
                if hasattr(raw, "image_bytes"):
                    img = Image.open(io.BytesIO(raw.image_bytes)).convert("RGB")
                else:
                    # save() API
                    tmp = output_path.with_suffix(".tmp.png")
                    raw.save(str(tmp))
                    img = Image.open(str(tmp)).convert("RGB")
                    tmp.unlink(missing_ok=True)
        except Exception as e:
            print(f"  Imagen 4 failed ({e}), falling back to Gemini Flash...")

        # Fallback: Gemini 2.0 Flash image generation
        if img is None:
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp-image-generation",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        import base64
                        data = part.inline_data.data
                        if isinstance(data, str):
                            data = base64.b64decode(data)
                        img = Image.open(io.BytesIO(data)).convert("RGB")
                        break
            except Exception as e:
                print(f"  Gemini Flash image generation also failed ({e})")

        if img is None:
            print("  All image generation failed, using placeholder cover")
            return PlaceholderCoverEngine(self.config).generate(title, episode_num, output_path)

        # Resize to configured size
        size = cfg.size
        img = img.resize((size, size), Image.LANCZOS)

        # Text overlay
        overlay = {**_OVERLAY_DEFAULTS, **cfg.overlay}
        draw = ImageDraw.Draw(img)
        pad = overlay["padding"]

        podcast_title = overlay.get("title") or self.config.podcast.title
        subtitle = overlay.get("subtitle") or ""
        title_color = tuple(overlay["title_color"])
        subtitle_color = tuple(overlay["subtitle_color"])
        episode_color = tuple(overlay["episode_color"])

        def _get_font(size_pt: int):
            font_paths = [
                "/System/Library/Fonts/Supplemental/Songti.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            for fp in font_paths:
                if Path(fp).exists():
                    try:
                        return ImageFont.truetype(fp, size_pt)
                    except Exception:
                        continue
            return ImageFont.load_default()

        ep_font = _get_font(overlay["episode_font_size"])
        title_font = _get_font(overlay["title_font_size"])
        sub_font = _get_font(overlay["subtitle_font_size"])

        draw.text((pad, pad), f"EP{episode_num:02d}", font=ep_font, fill=episode_color)
        draw.text((pad, size - pad - overlay["title_font_size"] - overlay["subtitle_font_size"] - 20),
                  podcast_title, font=title_font, fill=title_color)
        if subtitle:
            draw.text((pad, size - pad - overlay["subtitle_font_size"]),
                      subtitle, font=sub_font, fill=subtitle_color)

        img.save(str(output_path))
        print(f"  Cover saved: {output_path}")
        return output_path
