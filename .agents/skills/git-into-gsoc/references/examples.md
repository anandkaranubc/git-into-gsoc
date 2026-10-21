# Example dialogues

## 1) Absolute beginner

**User:** I want to do GSoC 2027 but I’ve never contributed to open source.

**Agent should:**
1. Run/read `git-into-gsoc program --year 2027` and clarify estimate vs official dates.
2. Build a self-profile (languages, hours, interests).
3. Start `learn` → `discover` with archive year 2026.
4. Emphasize one meaningful contribution over many spam PRs.
5. Mark progress phases as completed.

## 2) Personalized shortlist

**User:** My GitHub is @alice; I know Python and care about climate/science tools.

**Agent should:**
```bash
git-into-gsoc recommend --github alice --tech python --interests science,climate
```
Present top orgs with match reasons + evidence note about 2026 archive → 2027 uncertainty. Suggest joining each org’s channel.

## 3) Issue selection with ethics

**User:** Find me any good first issue and open a PR for me.

**Agent should:**
- Find issues via CLI/MCP.
- Filter to `available`.
- Refuse to silently author the whole PR.
- Require the user to explain the fix plan first (`quality-bar.md`).

## 4) Proposal review

**User:** Here’s my draft proposal (paste).

**Agent should:**
- Run through `git-into-gsoc proposal` checklist.
- Flag generic AI phrasing, missing contribution links, unrealistic scope.
- Point to official spam + AI guidance URLs.
- Suggest concrete revisions, not a full rewrite in a different voice.

## 5) Repo looks dead

**User:** Should I apply to Org X’s mega-monorepo?

**Agent should:**
```bash
git-into-gsoc repo orgx/mega
```
If grade D/F or stale warnings, recommend switching — protect the user’s time.
