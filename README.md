# dodo-skills

Reusable AI agent skills for Claude Code and other coding agents. Includes a meeting follow-up email drafter and a voice memo → Notion pipeline.

[![skills.sh](https://skills.sh/b/callmejustdodo/dodo-skills)](https://skills.sh/callmejustdodo/dodo-skills)

## Install

```bash
npx skills add callmejustdodo/dodo-skills
```

Or install a single skill:

```bash
npx skills add callmejustdodo/dodo-skills --skill followup-mail
npx skills add callmejustdodo/dodo-skills --skill voice-memo-to-notion
```

## Skills

| Skill | What it does |
|-------|--------------|
| [`followup-mail`](./followup-mail) | Drafts a Korean meeting follow-up email and saves it as a Gmail draft (never sends). |
| [`voice-memo-to-notion`](./voice-memo-to-notion) | Transcribes audio (ElevenLabs Scribe v2), summarizes, and creates a Notion page. |

## Prerequisites

| Dependency | Required by | Install |
|------------|-------------|---------|
| [`gws`](https://github.com/nicholasgasior/gws) | followup-mail | See gws docs |
| [`ntn`](https://ntn.dev) | voice-memo-to-notion | `curl -fsSL https://ntn.dev \| bash` |
| `ELEVENLABS_API_KEY` | voice-memo-to-notion | [elevenlabs.io](https://elevenlabs.io) |
| `ffprobe` | voice-memo-to-notion | `brew install ffmpeg` |
| `python3` + `elevenlabs` SDK | voice-memo-to-notion | `pip install elevenlabs` |

## Setup

1. **Clone and link:**

```bash
git clone https://github.com/callmejustdodo/dodo-skills.git
cd dodo-skills
./link.sh
```

2. **Configure `.env`:**

```bash
cp .env.example .env
$EDITOR .env
```

Fill in your personal values — Notion workspace/database IDs, email, etc. See `.env.example` for descriptions of each variable.

3. **Set API keys in your shell** (not in `.env`):

```bash
export ELEVENLABS_API_KEY=sk-...
```

4. **Authenticate external CLIs:**

```bash
ntn login        # Notion
gws auth login   # Google Workspace (Gmail)
```

## Usage

### followup-mail

Trigger by saying things like:
- "팔로업 메일 써줘"
- "미팅 후속 메일 초안"
- "follow-up draft"

The skill gathers meeting details, drafts a Korean business email, and saves it as a Gmail draft. It **never sends** — you review and send from Gmail.

### voice-memo-to-notion

Trigger by saying things like:
- "최근 보이스메모 노션에 올려줘"
- "이 파일 전사해서 노션에 저장"
- "transcribe and save to Notion"

The skill:
1. Picks up audio from Apple Voice Memos or an explicit file path
2. Transcribes via ElevenLabs Scribe v2 (with speaker diarization for meetings)
3. Generates a structured summary (thematic Q&A for meetings, detailed write-up for lectures)
4. Creates a Notion page with the summary + a raw transcript sub-page

## Config (`.env`)

Personal values — emails, Notion workspace/database/data-source IDs — live in a
gitignored `.env` at the repo root, **not** in the SKILL.md files.

Key variables:

| Variable | Purpose |
|----------|---------|
| `FOLLOWUP_FROM_NAME` | Signature name for follow-up emails |
| `FOLLOWUP_TO` | Default recipient email |
| `FOLLOWUP_SUBJECT_TAG` | Subject prefix, e.g. `[MyCompany]` |
| `NOTION_WS_PRIMARY` | Primary Notion workspace UUID |
| `NOTION_WS_LEGACY` | Secondary/legacy workspace UUID |
| `NOTION_PRIMARY_MEETING_DB` | Meeting Notes database ID |
| `NOTION_PRIMARY_MEETING_DS` | Meeting Notes data_source ID |

See `.env.example` for the full list.

## Manual Linking

If you prefer not to use `npx skills add`, you can symlink directly:

```bash
./link.sh            # symlink all skills into ~/.claude/skills and ~/.agents/skills
./link.sh <name>     # link a single skill
```

## Adding a New Skill

1. Create `<skill-name>/SKILL.md` in this repo (add `references/`, `TEMPLATE.md`, etc. as needed).
2. Put any personal/secret values in `.env` (+ document them in `.env.example`) and reference them as `$VARS` in the skill.
3. Run `./link.sh <skill-name>`.
4. Commit.

## License

MIT
