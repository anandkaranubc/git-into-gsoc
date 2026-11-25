"""Write a page for each published video, and the videos index, into the site folder.

    python3 scripts/build_videos.py              # writes site/videos/ pages and adds them to site/sitemap.xml
    python3 scripts/build_videos.py --out DIR    # writes somewhere else (tests)

site/videos/videos.json lists the published videos; CONTRIBUTING.md ("Adding a video")
says how to add one. Each page pairs the video with its chapters, a transcript, and the
guide page or tool to try after a chapter, so a visitor can act on what they watched.
The player loads from YouTube only when the visitor presses play (site/video.js): until
then the page makes no request to YouTube, which is what docs/privacy.md promises.
The Pages workflow runs this after build_docs.py, and the pages it writes are not committed.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from html import escape
from itertools import pairwise
from pathlib import Path
from typing import Any

from build_docs import add_to_sitemap
from build_site import FOOT, SITE_URL, _head, breadcrumbs

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site" / "videos"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
STAMP = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})")
# YouTube shows chapters only when the first starts at 0:00 and each lasts 10 seconds or more.
MIN_CHAPTER = 10
TRANSCRIPT_LINE = re.compile(r"\*\*\[([\d:]+)\]\*\* (.+)")


def seconds(stamp: str) -> int:
    """'1:02:03' or '2:03' as seconds; anything else raises ValueError."""
    match = STAMP.fullmatch(stamp)
    if not match:
        raise ValueError(f"not a timestamp: {stamp!r}")
    hours, minutes, secs = (int(g or 0) for g in match.groups())
    return hours * 3600 + minutes * 60 + secs


def iso_duration(total: int) -> str:
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "PT" + (f"{hours}H" if hours else "") + (f"{minutes}M" if minutes else "") + f"{secs}S"


def load(source: Path = SOURCE) -> dict[str, Any]:
    """The registry, checked, so a typo fails the build instead of shipping a broken page."""
    registry = json.loads((source / "videos.json").read_text(encoding="utf-8"))
    slugs: set[str] = set()
    for video in registry["videos"]:
        name = video.get("slug", "?")
        if not SLUG.fullmatch(name) or name in slugs:
            raise ValueError(f"{name}: slug must be unique, lowercase letters, digits and hyphens")
        slugs.add(name)
        if not VIDEO_ID.fullmatch(video["id"]):
            raise ValueError(f"{name}: id must be the 11 characters after watch?v=")
        if datetime.fromisoformat(video["published"]).utcoffset() is None:
            raise ValueError(f"{name}: published needs a time zone, as YouTube shows it")
        if len(video["description"]) > 160:
            raise ValueError(f"{name}: description is over 160 characters")
        starts = [seconds(c["at"]) for c in video.get("chapters", [])]
        if starts and (starts[0] != 0 or any(b - a < MIN_CHAPTER for a, b in pairwise(starts))):
            raise ValueError(f"{name}: chapters must start at 0:00 and be 10 seconds apart")
        if starts and starts[-1] >= video["seconds"]:
            raise ValueError(f"{name}: a chapter starts after the video ends")
        for key in ("thumbnail", "transcript"):
            if video.get(key) and not (source / video[key]).is_file():
                raise ValueError(f"{name}: {key} file {video[key]} is missing from {source}")
    return registry


def watch_url(video_id: str, at: int = 0) -> str:
    return f"https://www.youtube.com/watch?v={video_id}" + (f"&t={at}s" if at else "")


def json_ld(data: dict[str, Any]) -> str:
    # Titles are typed by hand: an escaped "<" keeps a "</script>" in one inert.
    text = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{text}</script>\n'


def video_object(video: dict[str, Any]) -> dict[str, Any]:
    """schema.org VideoObject with the fields Google's video results read."""
    return {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": video["title"],
        "description": " ".join(video["summary"]) or video["description"],
        "thumbnailUrl": [
            f"{SITE_URL}videos/{video['thumbnail']}",
            f"https://i.ytimg.com/vi/{video['id']}/maxresdefault.jpg",
        ],
        "uploadDate": video["published"],
        "duration": iso_duration(video["seconds"]),
        "embedUrl": f"https://www.youtube.com/embed/{video['id']}",
        "inLanguage": "en",
    }


def _day(stamp: str) -> str:
    at = datetime.fromisoformat(stamp)
    return f"{at.day} {at:%b %Y}"


def _clock(total: int) -> str:
    hours, rest = divmod(total, 3600)
    return (f"{hours}:{rest // 60:02}" if hours else f"{rest // 60}") + f":{rest % 60:02}"


def _minutes(total: int) -> str:
    return f"{round(total / 60)} min"


def transcript_html(text: str, video_id: str) -> str:
    """The transcript file as sections: '## 0:36 Title' headings and '**[0:36]** text' lines."""
    out = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block.startswith("## "):
            stamp, _, title = block[3:].partition(" ")
            out.append(f"<h3>{escape(title)}</h3>")
        elif match := TRANSCRIPT_LINE.fullmatch(block):
            stamp, words = match.groups()
            at = seconds(stamp)
            out.append(
                f'<p><a class="at" href="{escape(watch_url(video_id, at))}" data-seek="{at}" '
                f'data-out="video/transcript">{escape(stamp)}</a> {escape(words)}</p>'
            )
    return "\n".join(out)


def player(video: dict[str, Any], thumb: str) -> str:
    """A link to the video on YouTube that site/video.js turns into the player on click.

    Without JavaScript, or if the embed fails, the visitor still reaches the video.
    """
    shape = " vertical" if video.get("vertical") else ""
    return (
        f'<div class="player{shape}" data-video="{escape(video["id"])}" data-title="{escape(video["title"])}">\n'
        f'  <a class="facade" href="{escape(watch_url(video["id"]))}" data-out="video/play">\n'
        f'    <img src="{escape(thumb)}" width="1280" height="720" alt="" fetchpriority="high">\n'
        '    <span class="play" aria-hidden="true"><svg viewBox="0 0 12 12"><path d="M3 2H4V3H5V4H6V5H7V7H6V8H5V9H4V10H3Z" transform="translate(1.5 0)"/></svg>'
        f"Play <small>{_clock(video['seconds'])}</small></span>\n"
        f'    <span class="visually-hidden">Play {escape(video["title"])}, {_minutes(video["seconds"])}</span>\n'
        "  </a>\n</div>\n"
    )


def video_page(video: dict[str, Any], channel: dict[str, str], transcript: str) -> str:
    slug = video["slug"]
    path = f"videos/{slug}/"
    root = "../../"
    title = video["title"]
    html = _head(
        title,
        video["description"],
        root,
        path,
        image=f"https://i.ytimg.com/vi/{video['id']}/maxresdefault.jpg",
        kind="video.other",
    )
    html += breadcrumbs(
        [
            ("git into gsoc", SITE_URL),
            ("Videos", f"{SITE_URL}videos/"),
            (title, f"{SITE_URL}{path}"),
        ]
    )
    html += json_ld(video_object(video))
    rows = []
    for chapter in video.get("chapters", []):
        at = seconds(chapter["at"])
        step = chapter.get("try")
        action = (
            f'<a class="try" href="{root}{escape(step["href"])}">{escape(step["text"])}</a>'
            if step
            else ""
        )
        rows.append(
            f'<li><a class="at" href="{escape(watch_url(video["id"], at))}" data-seek="{at}" '
            f'data-out="video/chapter">{escape(chapter["at"])}</a>'
            f'<span class="name">{escape(chapter["title"])}</span>{action}</li>'
        )
    summary = "".join(f"<p>{escape(p)}</p>" for p in video["summary"])
    transcript_block = (
        f"""    <h2 id="transcript">Transcript</h2>
    <details class="transcript">
      <summary>Read the transcript</summary>
{transcript_html(transcript, video["id"])}
    </details>
"""
        if transcript
        else ""
    )
    html += f"""  <div class="wrap">
  <article class="doc video">
    <nav class="crumbs" aria-label="Breadcrumb"><a href="{root}">git into gsoc</a> / <a href="../">Videos</a></nav>
    <h1>{escape(title)}</h1>
    <p class="meta">{_minutes(video["seconds"])} · {_day(video["published"])} · <a href="{escape(channel["url"])}">{escape(channel["name"])}</a> on YouTube</p>
{player(video, root + "videos/" + video["thumbnail"])}    <p class="fine">Plays from YouTube. <a href="{escape(watch_url(video["id"]))}">Watch on YouTube</a> instead.</p>
    {summary}
    <h2 id="chapters">Chapters</h2>
    <ol class="chapters">{"".join(rows)}</ol>
    <aside class="next" aria-labelledby="next-title">
      <h2 id="next-title">Find organizations that fit you</h2>
      <p>Answer four questions and get three organizations to try a first pull request with.</p>
      <p><a class="btn" href="{root}start/">git in</a> <a href="{root}orgs/">or browse every organization</a></p>
    </aside>
{transcript_block}  </article>
  </div>
<script src="{root}video.js" defer></script>
"""
    return html + FOOT


def index_page(registry: dict[str, Any]) -> str:
    channel = registry["channel"]
    items = []
    for video in registry["videos"]:
        items.append(
            f'<li><a class="thumb" href="{escape(video["slug"])}/" tabindex="-1" aria-hidden="true">'
            f'<img src="{escape(video["thumbnail"])}" width="1280" height="720" alt="" loading="lazy"></a>'
            f'<div><h2><a href="{escape(video["slug"])}/">{escape(video["title"])}</a></h2>'
            f'<p class="meta">{_minutes(video["seconds"])} · {_day(video["published"])}</p>'
            f"<p>{escape(video['description'])}</p></div></li>"
        )
    description = (
        "Videos on getting into Google Summer of Code and open source, each with chapters, "
        "a transcript, and the guide step or tool to try next."
    )
    html = _head("Videos | git into gsoc", description, "../", "videos/")
    html += breadcrumbs([("git into gsoc", SITE_URL), ("Videos", f"{SITE_URL}videos/")])
    html += f"""  <div class="wrap">
  <article class="doc videos">
    <h1>Videos</h1>
    <p>Videos on getting into Google Summer of Code and open source, by <a href="{escape(channel["url"])}">{escape(channel["name"])}</a>, who builds git into gsoc.</p>
    <ol class="video-list">{"".join(items)}</ol>
  </article>
  </div>
"""
    return html + FOOT


def build(out: Path, source: Path = SOURCE) -> list[str]:
    """Write the videos pages under ``out`` and return their site paths."""
    registry = load(source)
    target = out / "videos"
    target.mkdir(parents=True, exist_ok=True)
    paths = ["videos/"]
    for video in registry["videos"]:
        transcript = (
            (source / video["transcript"]).read_text(encoding="utf-8")
            if video.get("transcript")
            else ""
        )
        (target / video["slug"]).mkdir(exist_ok=True)
        (target / video["slug"] / "index.html").write_text(
            video_page(video, registry["channel"], transcript), encoding="utf-8"
        )
        paths.append(f"videos/{video['slug']}/")
    (target / "index.html").write_text(index_page(registry), encoding="utf-8")
    if source.resolve() != target.resolve():
        for video in registry["videos"]:
            (target / video["thumbnail"]).write_bytes((source / video["thumbnail"]).read_bytes())
    add_to_sitemap(out / "sitemap.xml", paths)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the video pages into the site folder.")
    parser.add_argument("--out", type=Path, default=ROOT / "site", help="site folder to write into")
    args = parser.parse_args(argv)
    paths = build(args.out)
    print(f"wrote {len(paths)} pages under {args.out / 'videos'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
