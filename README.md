# claude-skills

Personal Claude Code / agent skills. **This repo is the source of truth.** Each skill
is symlinked into `~/.claude/skills/` and `~/.agents/skills/` — never edit the copies
there, edit here.

## Skills

| Skill | What it does |
|-------|--------------|
| [`followup-mail`](./followup-mail) | Drafts a Korean meeting follow-up email and saves it as a Gmail draft (never sends). |
| [`voice-memo-to-notion`](./voice-memo-to-notion) | Transcribes audio (ElevenLabs Scribe v2), summarizes, and creates a Notion page. |

## Config (`.env`)

Personal values — emails, Notion workspace/database/data-source IDs — live in a
gitignored `.env` at the repo root, **not** in the SKILL.md files. Copy the template
and fill it in:

```bash
cp .env.example .env
$EDITOR .env
```

Skills load it at runtime before any command that needs a value:

```bash
set -a; source ~/Developer/dodo-skills/.env; set +a
```

API keys (`ELEVENLABS_API_KEY`, `NOTION_API_TOKEN`) stay in your shell environment as
before — they are not stored in this repo.

## Linking

```bash
./link.sh            # symlink every skill into ~/.claude/skills and ~/.agents/skills
./link.sh <name>     # link a single skill
```

## Adding a new skill

1. Create `<skill-name>/SKILL.md` in this repo (add `references/`, `TEMPLATE.md`, etc. as needed).
2. Put any personal/secret values in `.env` (+ document them in `.env.example`) and
   reference them as `$VARS` in the skill.
3. Run `./link.sh <skill-name>`.
4. Commit.
