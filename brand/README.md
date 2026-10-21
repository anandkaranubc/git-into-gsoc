# git into gsoc brand

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="readme/banner-dark.svg">
  <img src="readme/banner-light.svg" alt="git into gsoc. open source has a door. git in." width="100%">
</picture>

Everything in this folder is generated from one pixel grid by `scripts/brand/build.py`. Edit the grid, run the script, commit the result. The pretty version of this page lives on the website at `site/brand.html`.

```bash
pip install fonttools brotli          # optional: builds the Gig Pixel font
python -m scripts.brand.build --raster  # SVG + tokens + font + PNG/ICO (PNG needs rsvg-convert, ICO needs ImageMagick)
python -m scripts.brand.preview         # stage site/ + brand/ and serve them locally
```

## The idea

The name is a pun on "get into". The mark takes it literally: the G is a doorway, the gap on its right side is the door, and the small block at the threshold is a terminal cursor stepping through. The cursor is always the person; the G is the community they are joining. It works for Git and for GSoC without borrowing either logo.

The cursor is the only thing allowed to move. It blinks at one beat per second in the README banner and on the website. Everything else stays still.

Both the mark and the typeface sit on a square grid with a thick stroke, so they are crisp at 16 px and still feel like one object on a T-shirt.

## Files

| Folder | What is in it |
|---|---|
| `logo/` | `mark-{light,dark,mono-ink,mono-paper}.svg`, `mark-tile*.svg`, `wordmark-*.svg`, `lockup-horizontal-*.svg`, `lockup-stacked-*.svg`, plus PNG renders |
| `favicon/` | `favicon.svg`, `favicon-16.svg` (hand-tuned 1x), `favicon.ico`, `favicon-16/32/48.png`, `apple-touch-icon.png`, `icon-192/512.png`, `app-icon.svg` |
| `avatar/` | `avatar.svg`, `avatar-512.png`, `avatar-1024.png`, `avatar-violet.svg` for the GitHub organization or repository picture |
| `social/` | `social-preview.svg` and `.png` at 1280×640 for GitHub's social preview and Open Graph |
| `readme/` | `banner-light.svg`, `banner-dark.svg` (animated cursor) and compact `header-*.svg` for docs |
| `icons/` | 14 pixel icons in ink, paper, and violet, plus `sheet-ink.svg` |
| `stickers/` | die-cut stickers: `git in.`, `merged.`, `the door is open.`, `evidence > vibes`, `no drive-by prs`, a blinking cursor |
| `stamps/` | passport-style milestone stamps: entered, discovered, evaluated, first pr, merged, proposed |
| `merch/` | `sticker-sheet.svg/.png`, `tee-back-dark.svg`, `tee-back-light.svg`, `tee-front-chest.svg` |
| `font/` | `GigPixel.woff2`, `GigPixel.ttf`, `specimen.svg/.png` |
| `tokens.css`, `tokens.json` | colour and type tokens, light/dark roles, measured contrast ratios |

## Logo rules

- On light backgrounds use `mark-light` (violet G, ink cursor). On dark backgrounds use `mark-dark` (violet G, lime cursor). `mark-tile` works on anything and is the avatar.
- Clear space: one cursor width (3 grid units) on every side.
- Below 48 px use the tile. The bare mark starts at 48 px. The favicon has a dedicated 16 px drawing.
- Scale in whole multiples of the grid where you can.
- Don't recolour outside the schemes, add gradients, outlines, or shadows, rotate, skew, or swap the cursor for an emoji, a dot, an arrow, or a Git branch icon.
- Don't place the mark next to the Google or Google Summer of Code logos or set it in their colours.
- The wordmark is a drawing, not a font setting. Don't retype it in another typeface.

## Colour

| Token | Hex | Role |
|---|---|---|
| merge | `#7A5AF8` | violet. The G. Fills and display text. The colour of a merged pull request. |
| merge-deep | `#4C2FD9` | text and links on paper (6.9:1) |
| merge-soft | `#C2B5FF` | text and links on ink (10:1) |
| open | `#C6F432` | lime. The cursor. Accents on ink only (14.4:1). Never text on paper. |
| open-deep | `#3F6A00` | success text on paper (5.8:1) |
| ink | `#15121E` | dark surfaces; text on paper (16.5:1) |
| ink-2 / ink-3 | `#211C2E` / `#332C47` | raised surfaces and borders on ink |
| paper | `#F4F1FA` | lavender-tinted off-white. Light surfaces; text on ink |
| paper-2 / paper-3 | `#E9E4F4` / `#CFC7E3` | raised surfaces and borders on paper |
| mute / mute-on-ink | `#67607A` / `#A49DB4` | secondary text |
| warn / danger | `#FFB224` / `#FF6A4D` | semantic states only |

`tokens.css` exposes these as `--gig-*` custom properties and maps them to roles (`--bg`, `--fg`, `--accent`, `--cursor`) that flip for dark mode.

## Type

- **Gig Pixel** (`font/`) is the brand face: lowercase only (uppercase maps to the same drawings), 2-cell stroke, 8-cell x-height. A cell is 1/16 em, so use it at 32, 48, 64, 80, or 96 px for whole-pixel rendering. Headlines, stickers, the tagline. Never body copy, never below 32 px.
- **Instrument Sans** (Google Fonts, system-ui fallback) for everything readable: 17 px body, 1.55 line height, sentence case, no all-caps labels.
- **System monospace** for code and terminal output.

## Voice

Lowercase, dry, warm. Short sentences, specific nouns, no hype.

- Yes: "open source has a door. git in." / "evidence > vibes." / "missing data is reported as missing."
- No: rocket emoji, "ultimate AI-powered", "guaranteed", anything implying Google built or endorsed this, slang for its own sake.

## Putting it on GitHub

These are repository settings, so they are done by hand once:

1. **Repository picture / organization avatar:** upload `avatar/avatar-512.png` (or `avatar-1024.png`).
2. **Social preview:** Settings → General → Social preview → upload `social/social-preview.png` (1280×640).
3. **Website:** Settings → Pages → Source: GitHub Actions. The `Pages` workflow stages `site/` with `brand/` and deploys on every push to `main` that touches them.
4. **README:** already uses `readme/banner-light.svg` and `banner-dark.svg` through a `<picture>` element, so it follows the reader's theme.

## Legal

All assets are original and MIT licensed with the rest of the repository. Use them to refer to the project, fork it, or make things for your community. Don't use them to suggest that Google, the Google Summer of Code program, or any GSoC organization made, sponsors, or endorses something. Google Summer of Code and GSoC are trademarks of Google LLC; this project is independent and the name is descriptive.
