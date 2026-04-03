"""RSS feed generation."""

import hashlib
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring, indent, register_namespace

from .config import PodcraftConfig
from .utils import get_duration, format_duration

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"

register_namespace("itunes", ITUNES_NS)
register_namespace("atom", ATOM_NS)


def format_rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_rss(episodes: list[dict], config: PodcraftConfig) -> str:
    """Build RSS XML string from episode list.

    Each episode dict: {
        "title": str,
        "description": str,
        "audio_file": str (local path for duration/size),
        "audio_url": str (remote URL),
        "pub_date": datetime,
        "episode_number": int,
    }
    """
    pc = config.podcast
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = pc.title
    SubElement(channel, "link").text = pc.link
    SubElement(channel, "language").text = pc.language
    SubElement(channel, "description").text = pc.description

    SubElement(channel, f"{{{ITUNES_NS}}}author").text = pc.author
    SubElement(channel, f"{{{ITUNES_NS}}}summary").text = pc.description
    if pc.cover_url:
        SubElement(channel, f"{{{ITUNES_NS}}}image", {"href": pc.cover_url})
    SubElement(channel, f"{{{ITUNES_NS}}}category", {"text": pc.category})
    SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = "false"

    if pc.email:
        owner = SubElement(channel, f"{{{ITUNES_NS}}}owner")
        SubElement(owner, f"{{{ITUNES_NS}}}name").text = pc.author
        SubElement(owner, f"{{{ITUNES_NS}}}email").text = pc.email

    for ep in episodes:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = ep["title"]
        SubElement(item, "description").text = ep["description"]

        from pathlib import Path
        audio_path = Path(ep["audio_file"])
        file_size = audio_path.stat().st_size if audio_path.exists() else 0
        duration = format_duration(get_duration(str(audio_path))) if audio_path.exists() else "00:00:00"

        SubElement(item, "enclosure", {
            "url": ep["audio_url"],
            "length": str(file_size),
            "type": "audio/mpeg",
        })

        guid = hashlib.md5(ep["title"].encode()).hexdigest()
        SubElement(item, "guid", {"isPermaLink": "false"}).text = guid
        SubElement(item, "pubDate").text = format_rfc822(ep["pub_date"])
        SubElement(item, f"{{{ITUNES_NS}}}duration").text = duration
        SubElement(item, f"{{{ITUNES_NS}}}episode").text = str(ep["episode_number"])
        SubElement(item, f"{{{ITUNES_NS}}}episodeType").text = "full"

    indent(rss, space="  ")
    xml_str = tostring(rss, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
