# PodCraft

Turn any Markdown into a two-person dialogue podcast with one command.

```
pip install podcraft
```

## Quick Start

```bash
# 1. Initialize a project
podcraft init --language en --title "My Podcast"

# 2. Set your LLM API key
export GEMINI_API_KEY=your-key-here

# 3. Publish an episode
podcraft publish episodes/my-article.md --title "EP01: My Topic"
```

## What It Does

PodCraft takes a Markdown document and turns it into a podcast episode:

1. **Script Generation** — LLM converts your document into natural two-person dialogue
2. **Audio Synthesis** — TTS engine voices both speakers with natural pacing
3. **RSS Feed** — Auto-generates a podcast feed you can import into any podcast app

## Pipeline

```
Markdown → LLM Script → TTS Audio → RSS Feed
```

## Features

- **One command** from document to podcast episode
- **Free by default** — Edge TTS requires no API key
- **Multi-language** — English, Chinese, Japanese out of the box
- **Configurable** — Custom prompts, voices, LLM engines
- **Multiple LLM backends** — Gemini, Claude, GPT-4o
- **Multiple TTS backends** — Edge TTS (free), Volcano Podcast API (high quality)

## Configuration

All settings live in `podcraft.yaml`:

```yaml
podcast:
  title: "My Podcast"
  language: "en"

hosts:
  host:
    name: "Alex"
    voice: "en-US-GuyNeural"
  guest:
    name: "Sam"
    voice: "en-US-JennyNeural"

llm:
  engine: "gemini"    # gemini, anthropic, openai

tts:
  engine: "edge"      # edge (free), volcano_podcast (paid)
```

## Commands

| Command | Description |
|---------|-------------|
| `podcraft init` | Initialize a new project |
| `podcraft publish <file>` | Full pipeline: document → audio |
| `podcraft script <file>` | Generate dialogue script only |
| `podcraft feed` | Regenerate RSS feed |

## Requirements

- Python 3.11+
- ffmpeg (for audio processing)
- An LLM API key (Gemini, Anthropic, or OpenAI)

## Installation

```bash
# Basic (Edge TTS only, free)
pip install podcraft

# With Gemini support
pip install "podcraft[gemini]"

# With all LLM backends
pip install "podcraft[all]"
```

## Chinese Podcast Example

```bash
podcraft init --language zh --title "我的播客"
export GEMINI_API_KEY=your-key
podcraft publish my-article.md --title "EP01: 有趣的话题"
```

## License

MIT
