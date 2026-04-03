"""Volcano Podcast TTS API (V3 WebSocket) - high quality, requires API key."""

import asyncio
import json
import os
import struct
import uuid
from pathlib import Path

import websockets

from ..config import PodcraftConfig

API_URL = "wss://openspeech.bytedance.com/api/v3/sami/podcasttts"
RESOURCE_ID = "volc.service_type.10050"
APP_KEY = "aGjiRDfUWi"

DEFAULT_SPEAKERS = [
    "zh_male_dayixiansheng_v2_saturn_bigtts",
    "zh_female_mizaitongxue_v2_saturn_bigtts",
]

HEADER = bytes([0x11, 0x14, 0x10, 0x00])

EVT_START_CONNECTION = 1
EVT_FINISH_CONNECTION = 2
EVT_CONNECTION_STARTED = 50
EVT_CONNECTION_FINISHED = 52
EVT_START_SESSION = 100
EVT_SESSION_STARTED = 150
EVT_SESSION_FINISHED = 152
EVT_PODCAST_ROUND_START = 360
EVT_PODCAST_ROUND_RESPONSE = 361
EVT_PODCAST_ROUND_END = 362
EVT_PODCAST_END = 363
EVT_USAGE_RESPONSE = 154


def _pre_frame(event: int, payload: dict) -> bytes:
    p = json.dumps(payload, ensure_ascii=False).encode()
    return HEADER + struct.pack(">I", event) + struct.pack(">I", len(p)) + p


def _post_frame(event: int, sid: str, payload: dict) -> bytes:
    sb = sid.encode()
    p = json.dumps(payload, ensure_ascii=False).encode()
    return (
        HEADER
        + struct.pack(">I", event)
        + struct.pack(">I", len(sb)) + sb
        + struct.pack(">I", len(p)) + p
    )


def _parse_response(data: bytes) -> dict:
    if len(data) < 4:
        return {"type": "unknown"}

    msg_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    has_event = (flags & 0x04) != 0
    offset = 4

    event_code = None
    if has_event and len(data) >= offset + 4:
        event_code = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4

    if msg_type == 0x0F:
        try:
            msg = data[offset:].decode("utf-8", errors="replace")
        except Exception:
            msg = data[offset:].hex()
        return {"type": "error", "event": event_code, "code": event_code, "message": msg}

    session_id = ""
    if len(data) > offset + 4:
        sid_len = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        if sid_len > 0 and len(data) >= offset + sid_len:
            session_id = data[offset:offset + sid_len].decode("utf-8", errors="replace")
            offset += sid_len

    remaining = data[offset:]

    if event_code == EVT_PODCAST_ROUND_RESPONSE:
        return {"type": "audio", "event": event_code, "session_id": session_id, "audio": remaining}

    if remaining:
        try:
            return {"type": "json", "event": event_code, "session_id": session_id,
                    "payload": json.loads(remaining.decode("utf-8"))}
        except Exception:
            pass
        if len(remaining) > 4:
            try:
                plen = struct.unpack(">I", remaining[:4])[0]
                if plen > 0 and len(remaining) >= 4 + plen:
                    return {"type": "json", "event": event_code, "session_id": session_id,
                            "payload": json.loads(remaining[4:4 + plen].decode("utf-8"))}
            except Exception:
                pass

    return {"type": "event", "event": event_code, "session_id": session_id}


class VolcanoPodcastEngine:
    def __init__(self, config: PodcraftConfig):
        self.config = config
        self.app_id = os.environ.get("VOLCANO_PODCAST_APP_ID", "")
        self.token = os.environ.get("VOLCANO_PODCAST_TOKEN", "")
        if not self.app_id or not self.token:
            raise RuntimeError("VOLCANO_PODCAST_APP_ID and VOLCANO_PODCAST_TOKEN must be set.")

    async def synthesize_dialogue(self, dialogue: list[dict], output_path: str) -> dict:
        speakers = DEFAULT_SPEAKERS
        role_to_speaker = {"host": speakers[0], "guest": speakers[1]}

        nlp_texts = []
        for turn in dialogue:
            text = turn["text"][:297] + "..." if len(turn["text"]) > 300 else turn["text"]
            nlp_texts.append({"speaker": role_to_speaker[turn["role"]], "text": text})

        payload = {
            "input_id": f"podcast_{uuid.uuid4().hex[:8]}",
            "action": 3,
            "nlp_texts": nlp_texts,
            "use_head_music": True,
            "use_tail_music": False,
            "audio_config": {"format": "mp3", "sample_rate": 24000, "speech_rate": 0},
            "input_info": {"return_audio_url": True},
        }

        headers = {
            "X-Api-App-Id": self.app_id,
            "X-Api-Access-Key": self.token,
            "X-Api-Resource-Id": RESOURCE_ID,
            "X-Api-App-Key": APP_KEY,
            "X-Api-Request-Id": str(uuid.uuid4()),
        }

        metadata = {"engine": "volcano_podcast", "duration": 0}
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as audio_file:
            async with websockets.connect(
                API_URL, additional_headers=headers,
                ping_interval=None, max_size=10 * 1024 * 1024,
            ) as ws:
                await ws.send(_pre_frame(EVT_START_CONNECTION, {}))
                resp = await asyncio.wait_for(ws.recv(), timeout=30)
                parsed = _parse_response(resp)
                if parsed.get("type") == "error":
                    raise RuntimeError(f"Connection error: {parsed}")
                session_id = parsed.get("session_id", "")

                await ws.send(_post_frame(EVT_START_SESSION, session_id, payload))

                rounds_completed = 0
                expected_rounds = len(nlp_texts)
                while True:
                    try:
                        timeout = 15 if rounds_completed >= expected_rounds else 300
                        resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        if rounds_completed > 0:
                            try:
                                await ws.send(_post_frame(EVT_FINISH_CONNECTION, session_id, {}))
                                await asyncio.wait_for(ws.recv(), timeout=5)
                            except Exception:
                                pass
                        break

                    parsed = _parse_response(resp)
                    if parsed["type"] == "error":
                        raise RuntimeError(f"Podcast API error: {parsed}")

                    event = parsed.get("event")

                    if event == EVT_PODCAST_ROUND_RESPONSE:
                        audio_data = parsed.get("audio", b"")
                        if audio_data:
                            audio_file.write(audio_data)
                    elif event == EVT_PODCAST_ROUND_END:
                        info = parsed.get("payload", {})
                        if isinstance(info, dict):
                            metadata["duration"] += info.get("audio_duration", 0)
                        rounds_completed += 1
                    elif event == EVT_PODCAST_ROUND_START:
                        info = parsed.get("payload", {})
                        text = info.get("text", "")
                        short = text[:50] + "..." if len(text) > 50 else text
                        print(f"  [Round {info.get('round_id', '?')}] {short}")
                    elif event == EVT_SESSION_FINISHED:
                        await ws.send(_post_frame(EVT_FINISH_CONNECTION, session_id, {}))
                    elif event == EVT_CONNECTION_FINISHED:
                        break

        return metadata
