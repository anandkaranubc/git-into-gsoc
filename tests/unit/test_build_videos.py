"""The video pages are generated from site/videos/videos.json, so a typo in an entry must
fail here, every "try" link must reach a page the site builds, and the page must not ask
YouTube for anything before the visitor presses play (docs/privacy.md)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_videos  # noqa: E402

PAGE = "videos/gsoc-rejection-to-mentor/index.html"


def _site(out: Path) -> Path:
    for script in ("build_site.py", "build_docs.py", "build_videos.py"):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--out", str(out)], check=True
        )
    return out


def _source(tmp_path: Path, **change: object) -> Path:
    source = tmp_path / "source"
    shutil.copytree(ROOT / "site" / "videos", source)
    registry = json.loads((source / "videos.json").read_text(encoding="utf-8"))
    registry["videos"][0].update(change)
    (source / "videos.json").write_text(json.dumps(registry), encoding="utf-8")
    return source


def test_every_chapter_link_reaches_a_page_the_site_builds(tmp_path: Path) -> None:
    out = _site(tmp_path)
    for video in build_videos.load()["videos"]:
        for chapter in video["chapters"]:
            if "try" in chapter:
                path, _, fragment = chapter["try"]["href"].partition("#")
                target = out / path / "index.html"
                assert target.is_file(), chapter
                if fragment:
                    assert f'id="{fragment}"' in target.read_text(encoding="utf-8"), chapter
    # The 2027 page and the home page link to the video, and the video page is in the sitemap.
    assert "videos/gsoc-rejection-to-mentor/" in (out / "gsoc-2027/index.html").read_text("utf-8")
    assert "videos/gsoc-rejection-to-mentor/" in (ROOT / "site/index.html").read_text("utf-8")
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert sitemap.count("<loc>https://gitintogsoc.me/videos/gsoc-rejection-to-mentor/</loc>") == 1


def test_a_video_page_sends_nothing_to_youtube_until_play(tmp_path: Path) -> None:
    build_videos.build(tmp_path)
    page = (tmp_path / PAGE).read_text(encoding="utf-8")
    assert "<iframe" not in page
    # og:image and the structured data name YouTube's thumbnail for crawlers; nothing a
    # browser fetches on its own (src, srcset, a stylesheet or preconnect link) points there.
    fetched = re.findall(r'(?:src|srcset)="([^"]+)"|<link[^>]+href="([^"]+)"', page)
    assert not [u for pair in fetched for u in pair if re.search(r"youtube|ytimg|ggpht", u)]
    assert (tmp_path / "videos/gsoc-rejection-to-mentor.webp").is_file()
    # Without JavaScript the picture and every time still open the video on YouTube.
    assert 'href="https://www.youtube.com/watch?v=RjqTWjdtIB8"' in page
    assert 'href="https://www.youtube.com/watch?v=RjqTWjdtIB8&amp;t=477s" data-seek="477"' in page
    assert "—" not in page


def test_video_page_metadata_is_valid_video_structured_data(tmp_path: Path) -> None:
    build_videos.build(tmp_path)
    page = (tmp_path / PAGE).read_text(encoding="utf-8")
    blocks = [
        json.loads(b)
        for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page)
    ]
    video = next(b for b in blocks if b["@type"] == "VideoObject")
    assert video["name"] == "From GSoC Rejection to Mentor: Lessons for GSoC 2027"
    assert video["uploadDate"] == "2026-11-23T05:00:09-08:00"
    assert video["duration"] == "PT24M32S"
    assert video["embedUrl"] == "https://www.youtube.com/embed/RjqTWjdtIB8"
    assert all(u.startswith("https://") for u in video["thumbnailUrl"])
    assert any(b["@type"] == "BreadcrumbList" for b in blocks)
    description = page.split('name="description" content="')[1].split('"')[0]
    assert 50 <= len(description) <= 160
    assert 'rel="canonical" href="https://gitintogsoc.me/videos/gsoc-rejection-to-mentor/"' in page
    assert 'property="og:type" content="video.other"' in page
    # The transcript is on the page, one time link per paragraph.
    assert page.count('data-out="video/transcript"') == 60


def test_a_title_cannot_end_the_structured_data_block(tmp_path: Path) -> None:
    source = _source(tmp_path, title="Evil</script><script>alert(1)</script>")
    build_videos.build(tmp_path / "out", source)
    page = (tmp_path / "out" / PAGE).read_text(encoding="utf-8")
    assert "<script>alert(1)" not in page


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"id": "RjqTWjdtIB"}, "11 characters"),
        ({"published": "2026-11-23T05:00:09"}, "time zone"),
        ({"chapters": [{"at": "0:05", "title": "Late start"}]}, "start at 0:00"),
        ({"chapters": [{"at": "0:00", "title": "a"}, {"at": "0:04", "title": "b"}]}, "10 seconds"),
        ({"chapters": [{"at": "0:00", "title": "a"}, {"at": "30:00", "title": "b"}]}, "after"),
        ({"thumbnail": "missing.webp"}, "missing"),
        ({"description": "x" * 161}, "160"),
        ({"slug": "Bad Slug"}, "slug"),
    ],
)
def test_a_bad_registry_entry_fails_the_build(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_videos.load(_source(tmp_path, **change))


def test_timestamps_and_durations() -> None:
    assert build_videos.seconds("7:57") == 477
    assert build_videos.seconds("1:02:03") == 3723
    assert build_videos.iso_duration(1472) == "PT24M32S"
    assert build_videos.iso_duration(3600) == "PT1H0S"
    with pytest.raises(ValueError):
        build_videos.seconds("7.57")
