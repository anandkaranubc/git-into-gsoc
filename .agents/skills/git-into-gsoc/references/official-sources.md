# Official sources (always prefer these)

## Canonical

| Resource | URL | Use for |
|----------|-----|---------|
| GSoC home | https://summerofcode.withgoogle.com | Announcements, org list, proposal submission |
| Program year page | https://summerofcode.withgoogle.com/programs/{YEAR} | Timeline & org directory for that year |
| Resources hub | https://developers.google.com/open-source/gsoc/resources | Guides, FAQ, contacts |
| Contributor guide | https://google.github.io/gsocguides/student/ | Proposals & community interaction |
| Mentor guide | https://google.github.io/gsocguides/mentor/ | How mentors evaluate contributors |
| AI tooling guidance | https://developers.google.com/open-source/gsoc/resources/ai_guidance | Org-varying AI rules; validate all AI output |
| Spam proposal guidance | https://developers.google.com/open-source/gsoc/resources/spam_proposals | Why generic LLM proposals fail |
| FAQ | https://developers.google.com/open-source/gsoc/faq | Eligibility, process Q&A |

## Archive data used by this toolkit

| Resource | URL | Notes |
|----------|-----|-------|
| GSoC Organizations API | https://api.gsocorganizations.dev/ | Community archive scraped from official GSoC pages — **not** a Google API |
| All orgs JSON | https://api.gsocorganizations.dev/organizations.json | 2016–latest |
| Year JSON | https://api.gsocorganizations.dev/{year}.json | e.g. `2026.json` |

When citing archive data, say it is archive-derived and must be confirmed on the official GSoC site for the target year.

## GSoC 2027 note

Until Google publishes 2027 dates and organizations:

1. Treat 2027 timeline entries from this toolkit as **planning estimates**.
2. Use **2026** org participation as the best available research base.
3. Continuously re-check https://summerofcode.withgoogle.com.

## AI policy summary (official themes)

- Org policies differ: some ban AI in proposals; some ban LLM code in the repo.
- Contributor retains **100% responsibility**; must fully understand submitted work.
- Best uses: research, learning, boilerplate, tests, refactoring, debugging — not opaque core logic.
- Blind trust and low-quality AI prose/code harm mentors and reduce acceptance odds.

Always re-read the official AI page and the specific org's GSoC docs before advising.
