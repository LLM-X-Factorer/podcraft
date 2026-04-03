[English](README_EN.md) | 中文

# PodCraft

一条命令，将任意 Markdown 文档变成双人对话播客。

```
pip install podcraft
```

## 快速开始

```bash
# 1. 初始化项目
podcraft init --language zh --title "我的播客"

# 2. 设置 LLM API Key
export GEMINI_API_KEY=your-key-here

# 3. 发布一期节目
podcraft publish episodes/my-article.md --title "EP01: 有趣的话题"
```

## 工作原理

PodCraft 将 Markdown 文档转化为播客节目：

1. **脚本生成** — LLM 将文档转写为自然的双人对话
2. **语音合成** — TTS 引擎为两位主播配音，带自然停顿
3. **RSS 订阅** — 自动生成播客 Feed，可导入任意播客 App

```
Markdown → LLM 对话脚本 → TTS 语音 → RSS Feed
```

## 特性

- **一条命令** — 从文档到播客一步到位
- **免费可用** — Edge TTS 无需 API Key
- **多语言** — 中文、英文、日文开箱即用
- **可配置** — 自定义提示词、声音、LLM 引擎
- **多 LLM 后端** — Gemini、Claude、GPT-4o
- **多 TTS 后端** — Edge TTS（免费）、火山引擎播客 API（高质量）

## 配置

所有设置在 `podcraft.yaml` 中：

```yaml
podcast:
  title: "我的播客"
  language: "zh"

hosts:
  host:
    name: "小明"
    voice: "zh-CN-YunxiNeural"
  guest:
    name: "小红"
    voice: "zh-CN-XiaoxiaoNeural"

llm:
  engine: "gemini"    # gemini, anthropic, openai

tts:
  engine: "edge"      # edge（免费）, volcano_podcast（付费）
```

## 命令

| 命令 | 说明 |
|------|------|
| `podcraft init` | 初始化新项目 |
| `podcraft publish <file>` | 完整管线：文档 → 音频 |
| `podcraft script <file>` | 仅生成对话脚本 |
| `podcraft feed` | 重新生成 RSS Feed |

## 环境要求

- Python 3.11+
- ffmpeg（音频处理）
- LLM API Key（Gemini、Anthropic 或 OpenAI）

## 安装

```bash
# 基础安装（仅 Edge TTS，免费）
pip install podcraft

# 带 Gemini 支持
pip install "podcraft[gemini]"

# 所有 LLM 后端
pip install "podcraft[all]"
```

## English Podcast Example

```bash
podcraft init --language en --title "My Podcast"
export GEMINI_API_KEY=your-key
podcraft publish my-article.md --title "EP01: My Topic"
```

## 许可证

MIT
