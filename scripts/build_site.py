"""Write the organization explorer: one web page per mentoring organization.

    python3 scripts/build_site.py              # writes site/orgs/ and site/sitemap.xml
    python3 scripts/build_site.py --out DIR    # writes somewhere else (tests)

The pages come from the same bundled snapshot the CLI reads offline
(``src/git_into_gsoc/data``), so a visitor sees what ``git-into-gsoc org`` would
show without installing anything. The Pages workflow runs this script, and the
output is not committed: it changes with every snapshot refresh. Only the standard
library is used so the workflow needs no install step.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "git_into_gsoc" / "data"
SITE_URL = "https://gitintogsoc.me/"
REPO_URL = "https://github.com/anandkaranubc/git-into-gsoc"
# A slug becomes a folder name, so anything else from the data is refused.
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
TECH_CHIPS = 18
CHANNEL_LABELS = {
    "mailingList": "Mailing list",
    "chat": "Chat",
    "email": "Email",
    "irc": "IRC",
    "forum": "Forum",
}


def load(data: Path = DATA) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    official = json.loads((data / "official_orgs.json").read_text("utf-8"))
    signals = json.loads((data / "org_signals.json").read_text("utf-8"))
    history = json.loads((data / "org_history.json").read_text("utf-8"))
    return official, signals, history


def _squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def history_for(name: str, history: dict[str, Any]) -> dict[int, int]:
    """Projects per year from the archive, matched by name since the archive has no slugs."""
    orgs = history.get("organizations") or {}
    entry = orgs.get(name)
    if entry is None:
        wanted = _squash(name)
        entry = next((v for k, v in orgs.items() if _squash(k) == wanted), {})
    years = (entry or {}).get("years") or {}
    return {int(y): int(v.get("num_projects") or 0) for y, v in years.items() if str(y).isdigit()}


def ideas_line(ideas: dict[str, Any], year: int | None) -> str:
    """The same sentence the CLI's evidence uses, so both surfaces agree."""
    count = int(ideas.get("count") or 0)
    when = f"{year} " if year else ""
    if not count:
        return "Its ideas page could not be split into separate ideas; read it yourself."
    line = f"{count} idea{'s' if count != 1 else ''} on its {when}ideas page"
    difficulty = {k: int(v) for k, v in (ideas.get("difficulty") or {}).items()}
    stated = sum(difficulty.values())
    if stated:
        spread = ", ".join(
            f"{difficulty[d]} {d}" for d in ("easy", "medium", "hard") if difficulty.get(d)
        )
        line += f"; of the {stated} that state a difficulty: {spread}"
    sizes = {k: int(v) for k, v in (ideas.get("size") or {}).items()}
    if sizes:
        spread = ", ".join(f"{sizes[s]} {s}" for s in ("small", "medium", "large") if sizes.get(s))
        line += f". Sizes: {spread}"
    mentors = int(ideas.get("mentors") or 0)
    if mentors:
        line += f". {mentors} mentor{'s' if mentors != 1 else ''} named"
    return line + "."


def _head(title: str, description: str, root: str, path: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{SITE_URL}{path}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:image" content="{SITE_URL}brand/social/social-preview.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#7A5AF8">
<link rel="icon" href="{root}brand/favicon/favicon.svg" type="image/svg+xml">
<link rel="icon" href="{root}brand/favicon/favicon-32.png" sizes="32x32" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap"></noscript>
<link rel="stylesheet" href="{root}brand/tokens.css">
<link rel="stylesheet" href="{root}styles.css">
<script>
  (function () {{
    var q = new URLSearchParams(location.search).get("theme");
    var t = q || (function () {{ try {{ return localStorage.getItem("gig-theme"); }} catch (e) {{ return null; }} }})();
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  }})();
</script>
</head>
<body>

<header class="wrap">
  <nav class="nav" aria-label="Main">
    <a class="brand" href="{root}" aria-label="git into gsoc, home">
      <svg class="tile" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="4.5" fill="#15121E"/><g transform="translate(1,2)"><path d="M0 2H1V1H2V0H18V1H19V2H20V6H16V4H5V5H4V15H5V16H10V12H20V18H19V19H18V20H2V19H1V18H0Z" fill="#7A5AF8"/><path d="M18 7H21V11H18Z" fill="#C6F432"/></g></svg>
      <span class="name pixel">git into gsoc</span>
    </a>
    <ul class="nav-links">
      <li><a href="{root}orgs/">organizations</a></li>
      <li class="optional"><a href="{root}docs/">guide</a></li>
      <li><a href="{REPO_URL}">github</a></li>
      <li><button class="theme-toggle" type="button" data-theme-toggle aria-pressed="false">dark</button></li>
    </ul>
  </nav>
</header>

<main>
"""


FOOT = """</main>

<footer class="footer">
  <div class="wrap cols">
    <div>
      <p class="tagline pixel">git in.<span class="cursor" aria-hidden="true"></span></p>
      <p>git into gsoc is an independent, MIT-licensed project. It is not affiliated with or endorsed by Google. Google Summer of Code and GSoC are trademarks of Google LLC. Verify dates, organizations, and rules on the <a href="https://summerofcode.withgoogle.com">official program site</a> and follow each organization's <a href="https://developers.google.com/open-source/gsoc/resources/ai_guidance">AI policy</a>.</p>
    </div>
    <ul>
      <li><a href="REPO/">Source on GitHub</a></li>
      <li><a href="https://pypi.org/project/git-into-gsoc/">Package on PyPI</a></li>
      <li><a href="SITE/docs/">Beginner guide</a></li>
      <li><a href="SITE/docs/sources/">Sources and limitations</a></li>
      <li><a href="REPO/issues/new?template=feedback.yml">Tell us how it went</a> (a public GitHub issue)</li>
    </ul>
  </div>
</footer>

<script>
  (function () {
    var root = document.documentElement;
    var btn = document.querySelector("[data-theme-toggle]");
    function current() {
      var set = root.getAttribute("data-theme");
      if (set) return set;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    function paint() {
      var dark = current() === "dark";
      btn.textContent = dark ? "light" : "dark";
      btn.setAttribute("aria-pressed", String(dark));
      btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    }
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("gig-theme", next); } catch (e) {}
      paint();
    });
    paint();
  })();
</script>
""".replace("REPO", REPO_URL).replace("SITE/", SITE_URL)

FILTER_SCRIPT = """<script>
  (function () {
    var cards = Array.prototype.slice.call(document.querySelectorAll(".org-card"));
    var search = document.getElementById("org-search");
    var category = document.getElementById("org-category");
    var chips = Array.prototype.slice.call(document.querySelectorAll("[data-tech-chip]"));
    var count = document.getElementById("org-count");
    var total = cards.length;
    function apply() {
      var words = search.value.toLowerCase().split(/\\s+/).filter(Boolean);
      var cat = category.value;
      var tech = chips.filter(function (c) { return c.getAttribute("aria-pressed") === "true"; })
        .map(function (c) { return c.getAttribute("data-tech-chip"); });
      var shown = 0;
      cards.forEach(function (card) {
        var text = card.getAttribute("data-search");
        var ok = words.every(function (w) { return text.indexOf(w) !== -1; })
          && (!cat || card.getAttribute("data-categories").split("|").indexOf(cat) !== -1)
          && tech.every(function (t) { return card.getAttribute("data-tech").split("|").indexOf(t) !== -1; });
        card.hidden = !ok;
        if (ok) shown += 1;
      });
      count.textContent = shown === total ? "all " + total + " organizations" : shown + " of " + total + " organizations";
    }
    search.addEventListener("input", apply);
    category.addEventListener("change", apply);
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        c.setAttribute("aria-pressed", c.getAttribute("aria-pressed") === "true" ? "false" : "true");
        apply();
      });
    });
    apply();
  })();
</script>
"""


def _link(url: str, text: str | None = None) -> str:
    """An anchor for a web address from the data; anything else (javascript:, mailto:) is shown as text."""
    if url.startswith(("https://", "http://")):
        return f'<a href="{escape(url)}">{escape(text or url)}</a>'
    return escape(text or url)


def _tags(values: list[str], label: str) -> str:
    if not values:
        return ""
    items = "".join(f"<li>{escape(v)}</li>" for v in values)
    return f'<ul class="clients" aria-label="{escape(label)}">{items}</ul>'


def _years_line(years: dict[int, int]) -> str:
    if not years:
        return "Not in the public archive yet (its first year, or listed under another name)."
    first = min(years)
    runs = ", ".join(f"'{y % 100:02d}: {n}" for y, n in sorted(years.items()))
    plural = "s" if len(years) != 1 else ""
    return f"In GSoC since {first}, {len(years)} year{plural}. Projects per year: {runs}."


def org_page(org: dict[str, Any], signal: dict[str, Any], years: dict[int, int], year: int) -> str:
    name = str(org["name"])
    tagline = str(org.get("tagline") or "")
    description = str(org.get("description") or "")
    ideas = signal.get("ideas") or {}
    github = signal.get("github") or {}
    quoted = name.replace('"', '\\"')

    links = []
    for label, url in (
        ("Website", org.get("website_url")),
        ("Ideas page", org.get("ideas_link")),
        ("Contributor guide", org.get("contributor_guidance_url")),
        ("Source code", org.get("source_code")),
    ):
        if url:
            links.append(f"<li>{label}: {_link(str(url))}</li>")
    for method in org.get("direct_comm_methods") or []:
        kind = str(method.get("name") or "")
        value = str(method.get("value") or "")
        if not value:
            continue
        label = CHANNEL_LABELS.get(kind, kind.capitalize() or "Contact")
        links.append(f"<li>{escape(label)}: {_link(value)}</li>")

    idea_items = "".join(
        "<li>"
        + escape(str(idea.get("t") or "Untitled idea"))
        + "".join(
            f' <span class="tag">{escape(str(idea[k]))}</span>' for k in ("s", "d") if idea.get(k)
        )
        + "</li>"
        for idea in ideas.get("ideas") or []
    )
    ideas_block = f"<p>{escape(ideas_line(ideas, year))}</p>"
    if idea_items:
        ideas_block += f'<ol class="ideas">{idea_items}</ol>'
    if ideas.get("url"):
        ideas_block += (
            f"<p>{_link(str(ideas['url']), 'Read the ideas page')}. "
            "Ideas are for scope reference; never copy one into a proposal.</p>"
        )

    languages = github.get("languages") or {}
    if github:
        ranked = sorted(languages.items(), key=lambda kv: -int(kv[1]))[:6]
        lang = ", ".join(f"{escape(k)} ({v})" for k, v in ranked)
        repos = int(github.get("active_repos") or 0)
        gh_block = (
            f"<p>{repos} repositor{'ies' if repos != 1 else 'y'} pushed to in the last year"
            + (f". Main languages: {lang}" if lang else "")
            + ".</p>"
        )
    else:
        gh_block = "<p>No GitHub organization found in its official listing.</p>"

    meta = f"GSoC {year} organization. {tagline}".strip()
    html = _head(f"{name}: GSoC {year} organization", meta, "../../", f"orgs/{org['slug']}/")
    html += f"""  <section class="section org" aria-labelledby="org-title">
    <div class="wrap">
      <p class="crumb"><a href="../">All organizations</a> · GSoC {year} · {escape(", ".join(org.get("categories") or []))}</p>
      <h1 id="org-title" class="org-name">{escape(name)}</h1>
      <p class="lede">{escape(tagline)}</p>
      <p>{escape(description)}</p>
      {_tags(org.get("tech_tags") or [], "Technologies")}
      {_tags(org.get("topic_tags") or [], "Topics")}
      <div class="two">
        <div>
          <h2>Project ideas</h2>
          {ideas_block}
          <h2>History</h2>
          <p>{escape(_years_line(years))}</p>
          <h2>On GitHub</h2>
          {gh_block}
        </div>
        <div>
          <h2>Links and channels</h2>
          <ul class="links">{"".join(links) or "<li>None listed.</li>"}</ul>
          <div class="term">
            <div class="term-bar"><span>go deeper in your terminal</span></div>
<pre><code>git-into-gsoc org "{escape(quoted)}" --shortlist
git-into-gsoc repos "{escape(quoted)}"
git-into-gsoc issues --org "{escape(quoted)}"</code></pre>
<pre aria-label="Or ask your assistant"><span class="k">or ask your assistant:</span>
<span class="v">"Which {escape(name)} repositories merge
newcomers' pull requests, and which beginner
issues are still free?"</span></pre>
          </div>
          <p class="fine">Those commands read live data: which repositories merge outside pull requests, and which beginner issues nobody has claimed. <a href="../../#install">Install in two minutes</a>.</p>
        </div>
      </div>
    </div>
  </section>
"""
    return html + FOOT


def index_page(
    orgs: list[dict[str, Any]],
    signals: dict[str, Any],
    history: dict[str, Any],
    year: int,
    generated: str,
) -> str:
    categories = sorted({c for org in orgs for c in org.get("categories") or []})
    tech_counts = Counter(t for org in orgs for t in org.get("tech_tags") or [])
    chips = "".join(
        f'<button type="button" class="chip" data-tech-chip="{escape(t)}" aria-pressed="false">'
        f"{escape(t)} <small>{n}</small></button>"
        for t, n in tech_counts.most_common(TECH_CHIPS)
    )
    options = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in categories)

    cards = []
    for org in orgs:
        slug = str(org["slug"])
        ideas = (signals.get(slug) or {}).get("ideas") or {}
        years = history_for(str(org["name"]), history)
        facts = []
        count = int(ideas.get("count") or 0)
        if count:
            facts.append(f"{count} idea{'s' if count != 1 else ''}")
            easy = int((ideas.get("difficulty") or {}).get("easy") or 0)
            if easy:
                facts.append(f"{easy} easy")
            small = int((ideas.get("size") or {}).get("small") or 0)
            if small:
                facts.append(f"{small} small")
        if org.get("contributor_guidance_url"):
            facts.append("contributor guide")
        if years:
            facts.append(f"since {min(years)}")
        search = " ".join(
            [
                str(org["name"]),
                str(org.get("tagline") or ""),
                *(org.get("tech_tags") or []),
                *(org.get("topic_tags") or []),
                *(org.get("categories") or []),
            ]
        ).lower()
        cards.append(
            f'<li class="org-card" data-search="{escape(search)}" '
            f'data-categories="{escape("|".join(org.get("categories") or []))}" '
            f'data-tech="{escape("|".join(org.get("tech_tags") or []))}">'
            f'<h2><a href="{escape(slug)}/">{escape(str(org["name"]))}</a></h2>'
            f"<p>{escape(str(org.get('tagline') or ''))}</p>"
            f"{_tags((org.get('tech_tags') or [])[:5], 'Technologies')}"
            f'<p class="facts">{escape(" · ".join(facts))}</p>'
            "</li>"
        )

    title = f"GSoC {year} organizations: find yours"
    description = (
        f"Every Google Summer of Code {year} mentoring organization, with its project ideas, "
        "difficulty, sizes, history, and channels. Filter by what you know. No install needed."
    )
    html = _head(title, description, "../", "orgs/")
    html += f"""  <section class="section org-index" aria-labelledby="orgs-title">
    <div class="wrap">
      <div class="section-head">
        <h1 id="orgs-title" class="pixel">which door is yours?</h1>
        <p>Every GSoC {year} mentoring organization from the <a href="https://summerofcode.withgoogle.com/programs/{year}/organizations">official list</a>, with what its ideas page offers and how long it has taken part. {year + 1} organizations are not announced yet; {year} participants are the best predictor of who returns. Snapshot of {escape(generated)}. Pick a few, then let the <a href="../#install">terminal tool</a> or your assistant check which repositories merge newcomers' work.</p>
      </div>
      <form class="filters" role="search" aria-label="Filter organizations" onsubmit="return false">
        <label>Search <input id="org-search" type="search" placeholder="name, language, topic" autocomplete="off"></label>
        <label>Category <select id="org-category"><option value="">any</option>{options}</select></label>
        <div class="chips" aria-label="Technologies">{chips}</div>
        <p class="fine" aria-live="polite">Showing <span id="org-count">all {len(cards)} organizations</span>.</p>
      </form>
      <ul class="orgs">{"".join(cards)}</ul>
    </div>
  </section>
"""
    return html + FOOT + FILTER_SCRIPT


def sitemap(slugs: list[str]) -> str:
    urls = [
        SITE_URL,
        f"{SITE_URL}brand.html",
        f"{SITE_URL}orgs/",
        *(f"{SITE_URL}orgs/{s}/" for s in slugs),
    ]
    body = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'
    )


def build(out: Path, data: Path = DATA) -> list[str]:
    """Write the explorer under ``out`` and return the slugs written."""
    official, signals, history = load(data)
    year = int(official.get("year") or 0)
    generated = str(official.get("generated") or "unknown date")
    by_slug = signals.get("organizations") or {}
    orgs = sorted(
        (
            o
            for o in official.get("organizations") or []
            if SLUG.fullmatch(str(o.get("slug") or ""))
        ),
        key=lambda o: str(o["name"]).lower(),
    )
    orgs_dir = out / "orgs"
    orgs_dir.mkdir(parents=True, exist_ok=True)
    slugs = []
    for org in orgs:
        slug = str(org["slug"])
        page = org_page(org, by_slug.get(slug) or {}, history_for(str(org["name"]), history), year)
        (orgs_dir / slug).mkdir(exist_ok=True)
        (orgs_dir / slug / "index.html").write_text(page, encoding="utf-8")
        slugs.append(slug)
    (orgs_dir / "index.html").write_text(
        index_page(orgs, by_slug, history, year, generated), encoding="utf-8"
    )
    (out / "sitemap.xml").write_text(sitemap(slugs), encoding="utf-8")
    return slugs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the organization explorer into the site folder."
    )
    parser.add_argument("--out", type=Path, default=ROOT / "site", help="site folder to write into")
    args = parser.parse_args(argv)
    slugs = build(args.out)
    print(f"wrote {len(slugs)} organization pages under {args.out / 'orgs'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
