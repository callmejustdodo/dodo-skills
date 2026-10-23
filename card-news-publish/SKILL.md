---
name: card-news-publish
description: "Send a finished card-news deck (Figma slides) to Slack for approval and publish it as an Instagram + Threads carousel when the approver presses [발행]. Registers decks, exports slides to JPEG plus a one-image preview grid, runs a rule-based Slack bot (Socket Mode) that posts the confirm request with captions and a confirm dialog, and uploads to a Supabase public bucket only at publish time. Use when the user says 카드뉴스 발행, 발행 컨펌 요청, 슬랙으로 컨펌 받아줘, 인스타/스레드에 올려줘, 캐러셀 발행, 'publish this carousel', 'send for approval', or wants to register a new deck with the confirm bot."
metadata:
  version: 0.1.0
  openclaw:
    category: "marketing"
---

# Card News Publish

Figma 카드뉴스 → Slack 컨펌 → 인스타그램·스레드 캐러셀 게시.

```
decks/<slug>/png  ──prepare_deck.py──▶  slides/*.jpg + preview.png
                                              │
 Slack 메시지(trigger) or confirm.py ─────────▶ 컨펌 요청 (미리보기 · 피그마 · 캡션 · [발행]/[발행 취소])
                                              │  [발행] → 확인창 → bot.py
                                              ▼
                   Supabase 공개 버킷 업로드 → 인스타 캐러셀 → 스레드 캐러셀 → 메시지에 링크
```

The bot is **rule-based** (no model calls): it matches text, waits, posts, and reacts to buttons.

## Rules

- **Nothing is published without a [발행] click from an allowed user** (`SLACK_ALLOWED_USERS`). There is
  deliberately no CLI publish command. Publishing is public and only reversible by deleting the post.
- Send a confirm request (`confirm.py`) only when the user asked for one.
- Images go to the public bucket **only at publish time**, never at confirm time.
- Never print `.env` values. Errors shown in Slack are redacted (`publisher.redact`).
- A deck that reworks someone else's post must carry a `warning` in `deck.json` saying the original
  author's permission is needed before publishing.

## Setup (once)

```bash
SKILL_DIR="$(readlink ~/.claude/skills/card-news-publish || echo ~/.claude/skills/card-news-publish)"
cp "$SKILL_DIR/.env.example" "$SKILL_DIR/.env" && chmod 600 "$SKILL_DIR/.env"
```

Fill in `$SKILL_DIR/.env` (gitignored, lives inside this skill folder):

| Key | Where |
|---|---|
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | Slack app → OAuth (bot `xoxb-`) and Basic Info → App-Level Token (`xapp-`, Socket Mode). Scopes used: `chat:write`, `files:write`, `files:read`, `channels:history`, `app_mentions:read`. Interactivity must be on. |
| `SLACK_CHANNEL`, `SLACK_ALLOWED_USERS` | Home channel ID; comma-separated user IDs who may approve (first one is @-mentioned). |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Meta app → Instagram → *API setup with Instagram login*; professional account; `instagram_business_basic`, `instagram_business_content_publish`; long-lived token (60 days). |
| `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN` | Meta app → Threads use case → add the account as a Threads tester → token with `threads_basic`, `threads_content_publish`. |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_BUCKET` | Project URL; secret key (`sb_secret_…`) or legacy `service_role`. The bucket (default `card-news`) is created public on first publish. `supabase projects api-keys --project-ref <ref> -o json` returns both if the CLI is logged in. |
| `PUBLISH_DRY_RUN` | `1` = run the whole approval flow but skip posting. |

Missing platform keys are not an error: [발행] still works and the result message says which
platform was skipped and why. Check readiness (prints no secrets):

```bash
cd "$SKILL_DIR" && uv run --with requests python scripts/publisher.py check
```

## Workflow

### 1. Register a deck

Create `decks/<slug>/` (gitignored) with:

- `deck.json`
  ```json
  {
    "title": "카드뉴스 제목",
    "summary": "한 줄 설명 (Slack mrkdwn, <url|text> 링크 가능)",
    "figma_url": "https://www.figma.com/design/<fileKey>/...?node-id=<section-id>",
    "figma_label": "카드뉴스 › 제목",
    "meta": "1080×1350 · 메모",
    "warning": "선택: 컨펌 메시지에 ⚠️로 표시할 주의 사항",
    "trigger": "선택: 이 문자열이 든 Slack 메시지에 반응 (예: 원본 인스타 게시물 ID)",
    "trigger_delay_sec": 30,
    "preview": {"eyebrow": "카드뉴스", "title": ["두 줄", "제목"], "lines": ["총 N장 · 1080×1350"], "colors": ["#A66BEE"]}
  }
  ```
- `captions.json` — `{"instagram": "≤2,200자, 해시태그 ≤30", "threads": "≤500자"}`. Omit a key to skip that platform.
  Write captions in the deck's language; credit the original creator when the deck adapts someone's post.
- `png/slide-01.png …` — export each slide frame from Figma: `get_screenshot` with the frame's
  `nodeId` and `maxDimension` = the frame's long edge (1350 for 1080×1350), then `curl` the returned URL.
  Keep slide order in the file names.

Then build the JPEGs (Instagram accepts JPEG only) and the preview grid, and **look at `preview.png`** before
sending anything:

```bash
uv run --with pillow python scripts/prepare_deck.py decks/<slug>
```

### 2. Start the bot (one instance)

```bash
cd "$SKILL_DIR" && uv run --with slack_bolt --with requests python -u scripts/bot.py
```

Run it in the background and watch its log for `trigger`, `posted confirm`, `decision`, `published`, `failed`.
It refuses to start twice (`state/bot.pid`). Decks are re-read on every message, so new decks need no restart.

Only one process should hold a Socket Mode connection for the Slack app; a second consumer (e.g. another
agent gateway using the same app token) splits events and button clicks between them. Check before starting.

### 3. Ask for confirmation

- **Rule-based trigger:** an allowed user posts a message containing the deck's `trigger` (e.g. the original
  post link) in any channel the bot can read; after `trigger_delay_sec` the bot posts the confirm request there.
- **Immediately:** `uv run --with slack_bolt --with requests python scripts/confirm.py <slug> [--channel C…]`.

The request shows the preview image, Figma link, both captions, and [발행]/[발행 취소]. [발행] opens a
"정말 발행할까요?" dialog first.

### 4. On [발행]

`publisher.publish_all`: validate slides/captions → create the public bucket if needed → upload
`<slug>/<timestamp>/slide-NN.jpg` → Instagram carousel (item containers → carousel → poll `status_code`
→ `media_publish` → permalink) → Threads carousel (same with `/threads`, `status`, `/threads_publish`).
The Slack message is updated with per-platform links or the redacted error. One platform failing does not
block the other. Logs: `state/decisions.jsonl`, `state/publish_log.jsonl`.

### 5. Maintenance

- Tokens expire after 60 days: `uv run --with requests python scripts/publisher.py refresh-tokens` (rewrites `.env`).
- Tests (local fake Supabase/Instagram/Threads servers, no network):
  `uv run --with requests --with pillow --with pytest python -m pytest -q scripts/test_publish.py`

## Files

```
card-news-publish/
├── SKILL.md
├── .env.example          # committed template
├── .env                  # real keys (gitignored)
├── decks/<slug>/         # deck data (gitignored)
├── state/                # pid, preview file ids, decision/publish logs (gitignored)
└── scripts/
    ├── bot.py            # Socket Mode bot: trigger → confirm request; buttons → publish
    ├── confirm.py        # post a confirm request now
    ├── prepare_deck.py   # PNG → JPEG + preview grid
    ├── publisher.py      # Supabase upload + Instagram/Threads carousel, check, refresh-tokens
    ├── messages.py       # Block Kit builders
    ├── slack_io.py       # preview upload cache, confirm posting
    ├── deck.py           # paths, .env, deck loading
    └── test_publish.py
```
