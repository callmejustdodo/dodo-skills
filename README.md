# dodo-skills

Reusable AI agent skills for Claude Code and other coding agents. Includes a meeting follow-up email drafter, a voice memo → Notion pipeline, and a macOS performance doctor.

[![skills.sh](https://skills.sh/b/callmejustdodo/dodo-skills)](https://skills.sh/callmejustdodo/dodo-skills)

## Install

```bash
npx skills add callmejustdodo/dodo-skills
```

Or install a single skill:

```bash
npx skills add callmejustdodo/dodo-skills --skill followup-mail
npx skills add callmejustdodo/dodo-skills --skill voice-memo-2-meeting-note
npx skills add callmejustdodo/dodo-skills --skill mac-lag-doctor
```

## Skills

| Skill | What it does |
|-------|--------------|
| [`followup-mail`](./followup-mail) | Drafts a Korean meeting follow-up email and saves it as a Gmail draft (never sends). |
| [`voice-memo-2-meeting-note`](./voice-memo-2-meeting-note) | Transcribes audio (ElevenLabs Scribe v2), summarizes, and creates a Notion page. |
| [`mac-lag-doctor`](./mac-lag-doctor) | Diagnoses macOS lag with evidence — A/B-tests every suspect before blaming it. |

## Prerequisites

| Dependency | Required by | Install |
|------------|-------------|---------|
| [`gws`](https://github.com/nicholasgasior/gws) | followup-mail | See gws docs |
| [`ntn`](https://ntn.dev) | voice-memo-2-meeting-note | `curl -fsSL https://ntn.dev \| bash` |
| `ELEVENLABS_API_KEY` | voice-memo-2-meeting-note | [elevenlabs.io](https://elevenlabs.io) |
| `ffprobe` | voice-memo-2-meeting-note | `brew install ffmpeg` |
| `python3` + `elevenlabs` SDK | voice-memo-2-meeting-note | `pip install elevenlabs` |

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

### voice-memo-2-meeting-note

Trigger by saying things like:
- "최근 보이스메모 노션에 올려줘"
- "이 파일 전사해서 노션에 저장"
- "transcribe and save to Notion"

The skill:
1. Picks up audio from Apple Voice Memos or an explicit file path
2. Transcribes via ElevenLabs Scribe v2 (with speaker diarization for meetings)
3. Generates a structured summary (thematic Q&A for meetings, detailed write-up for lectures)
4. Creates a Notion page with the summary + a raw transcript sub-page

### mac-lag-doctor

Trigger by saying things like:
- "맥이 렉 걸려", "요즘 느려", "메모리 너무 많이 먹는 것 같아"
- "why is my mac slow", "what's eating my CPU"

No config, no API keys — everything it uses ships with macOS.

```bash
mac-lag-doctor/scripts/snapshot.sh          # baseline: CPU lane vs memory lane
mac-lag-doctor/scripts/ab-test.sh "Siri AI" # quit → measure → verdict → restore
```

The core discipline: **never blame a process you have not A/B-tested.** The snapshot
splits CPU-bound from memory-bound causes, flags stuck processes (high CPU for the
full uptime) and duplicated helpers/MCP servers, and reads Claude Code's daemon spare
state so claimed sessions aren't killed by mistake.

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
