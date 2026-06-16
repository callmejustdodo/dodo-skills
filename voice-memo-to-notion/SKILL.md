---
name: voice-memo-to-notion
description: Transcribe an audio file via ElevenLabs Scribe v2 (diarized for meetings, plain for lectures), summarize it, and create a Notion page (summary + raw transcript) under the configured database. Can pull recordings straight from the macOS Apple Voice Memos app (auto-reads the latest/by-date memo from its local library — no manual export needed), or take an explicit audio/video file. Use when the user provides a file or references a voice memo and asks to "send it to Notion", "log this meeting", "transcribe my latest voice memo", "transcribe and save to Notion", or similar audio→Notion pipeline requests.
---

# Voice Memo → Notion

End-to-end pipeline that turns an audio recording into a Notion page containing both an LLM-generated summary and the full transcript. Transcription is **always ElevenLabs Scribe v2** (`scribe_v2`) — single-request up to 3 GB / 10 hr, native diarization, supports `keyterms` (up to 100) for biasing. The previous OpenAI path was removed after an A/B test on Korean lecture audio: Scribe v2 produced cleaner output, captured audio events, and didn't suffer the prompt-bleed bug that polluted `gpt-4o-transcribe` runs.

Two transcription modes are supported and auto-routed by content type:

- **diarized** (회의/미팅) — `scribe_v2` with `diarize=true`. Speaker labels (`speaker_0`, `speaker_1`, …) are stable across the whole file (one pass, no chunk reset).
- **plain transcribe** (강연/세미나/교육) — `scribe_v2` with `diarize=false`. No speaker labels — just running text with word-level timestamps.

Composes two existing skills:
- `speech-to-text` — ElevenLabs Scribe v2 reference (Python SDK / cURL examples).
- `notion-cli` — Notion API access via the `ntn` command.

## Inputs

Two source modes — pick whichever fits the user's request:

### Mode A: explicit file
- `audio_file` (required): absolute or relative path to a local audio/video file (wav/mp3/m4a/mp4/etc.).
- `title` (optional): override for the Notion page title. Default: audio filename without extension.

### Mode B: Apple Voice Memos picker
Triggered when the user says "voice memo", "latest recording", "yesterday's memo", etc.

Source-of-truth: the SQLite metadata DB at
`~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/CloudRecordings.db`.

Reading this directory requires Full Disk Access for the terminal/binary running
Claude Code (System Settings → Privacy & Security → Full Disk Access). If access
is blocked, fall back to telling the user to drag the memo into `~/Downloads`.

Schema (verified):
- Table `ZCLOUDRECORDING`
- `ZENCRYPTEDTITLE` — **the user-renamed title shown in the app** (plaintext on
  read despite the column name; Apple kept the legacy name). This is what to use.
- `ZCUSTOMLABEL` — legacy/derived label, often an ISO timestamp like
  `2026-04-23T10:12:19Z`. Use only as a fallback.
- `ZPATH` — filename relative to the `Recordings/` directory
- `ZDATE` — Core Data timestamp (seconds since 2001-01-01 UTC). Convert to unix epoch with `ZDATE + 978307200`.
- `ZDURATION` — seconds

Title precedence: `ZENCRYPTEDTITLE` → `ZCUSTOMLABEL` (only if it doesn't match
`^\d{4}-\d{2}-\d{2}T`, i.e. not the auto timestamp) → filename without extension.

Pick the latest recording:

```bash
VM_DIR="$HOME/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
sqlite3 -separator $'\t' "$VM_DIR/CloudRecordings.db" \
  "SELECT ZENCRYPTEDTITLE, ZCUSTOMLABEL, ZPATH, ZDURATION
   FROM ZCLOUDRECORDING ORDER BY ZDATE DESC LIMIT 1;"
# → title<TAB>label<TAB>filename.m4a<TAB>duration
```

If the DB seems stale (the user just renamed and it's not showing), force a
WAL checkpoint first — Voice Memos may not have flushed yet:

```bash
sqlite3 "$VM_DIR/CloudRecordings.db" "PRAGMA wal_checkpoint(FULL);"
```

For "from <date>" requests, filter on `ZDATE`:

```bash
# everything recorded yesterday (UTC), newest first
sqlite3 "$VM_DIR/CloudRecordings.db" \
  "SELECT ZENCRYPTEDTITLE, ZPATH FROM ZCLOUDRECORDING
   WHERE datetime(ZDATE + 978307200, 'unixepoch') >= date('now','-1 day')
     AND datetime(ZDATE + 978307200, 'unixepoch') <  date('now')
   ORDER BY ZDATE DESC;"
```

The full audio path is then `$VM_DIR/$ZPATH`.

### Common options
- `database_id` (optional): override the default target database.
- `language` (optional): language hint passed through to Scribe v2 as `language_code`. **Always confirm this with the user before transcription** (default suggestion: 한국어 / `kor`). If the user gave the input but didn't specify a language, ask: *"한국어로 진행하면 될까요? (다른 언어면 알려주세요)"* — never silently assume. Scribe v2 accepts ISO 639-1 (`ko`, `en`) or 639-3 (`kor`, `eng`); normalize to 639-3 (`kor`, `eng`, `jpn`, `zho`) for consistency.
- `mode` (optional): `diarize` or `transcribe`. Auto-detected from title (see "Transcription mode routing" below); explicit value always wins.
- `keyterms` (optional): list of up to 100 names/terms to bias the recognizer toward (company names, product names, speaker names, technical jargon, acronyms). Strongly recommended when the audio mentions proper nouns ASR is likely to mangle.

## Target database

Two `Meeting Notes` databases exist; pick by content type. Both share the same
schema below.

### Config (.env)

All workspace / database / data-source IDs live in the repo `.env`, not inline here.
Load them once at the top of the run, before any `ntn` call:

```bash
set -a; source ~/Developer/dodo-skills/.env; set +a
```

This defines `$NOTION_WS_SCENIC`, `$NOTION_WS_DODO`, `$NOTION_USER`, `$NOTION_1ON1_DS`,
`$NOTION_1ON1_DB`, `$NOTION_1ON1_PARENT_PAGE`, `$NOTION_SCENIC_MEETING_DB`,
`$NOTION_SCENIC_MEETING_DS` (the **default** meeting target, in Scenic),
`$NOTION_MEETING_DB`, `$NOTION_MEETING_DS`, `$NOTION_DEFAULT_DB`, `$NOTION_DEFAULT_DS`
(the last four are legacy DODO-SPACE DBs). If any are unset, the `.env` is missing —
tell the user to `cp .env.example .env` and fill it in.

### Workspace (pinned)

**Default workspace is Scenic** (`$NOTION_WS_SCENIC`) as of 2026-06-07 — the user asked
to make Scenic the default going forward. The `ntn` CLI's default workspace is **not
stable** — it gets overwritten to whatever workspace `NOTION_WORKSPACE_ID` last
targeted, so every `ntn api` call 404s with `Could not find data_source` if the pin
drifts. **Always pin the workspace for this skill** by exporting it once at the top of
the run, before any `ntn` call:

```bash
export NOTION_WORKSPACE_ID=$NOTION_WS_SCENIC  # Scenic (default)
```

This env var overrides the config default for the whole session. Verify with
`ntn api v1/users/me` → `bot.workspace_name` should read `Scenic`. If the workspace
isn't in `~/.config/notion/workspaces.json`, the user must `ntn login` to it first.
(Stored workspace ids: Scenic = `$NOTION_WS_SCENIC`, DODO-SPACE = `$NOTION_WS_DODO`.)

**As of 2026-06-14 the default target for meetings/미팅/everything else is the
Scenic `Meeting Notes` DB** (`$NOTION_SCENIC_MEETING_DS`) — created with the default
Scenic pin above, no re-pin needed. The legacy `Meeting Notes` DBs (회의록 / old default)
live in **DODO-SPACE** and are used **only when the user explicitly routes there** (or
passes an explicit `database_id`); for those, re-pin `NOTION_WORKSPACE_ID` to
`$NOTION_WS_DODO` for that run, or every call 404s.

### Routing

- **1on1 (원온원):** title/label contains `1on1`, `1:1`, `원온원`, or `one on one`
  (case-insensitive). **This is the default for 1on1s and lives in Scenic.**
  - Workspace: **Scenic** (`$NOTION_WS_SCENIC`)
  - Private DB `1on1 Notes`, under the 🔒 `1on1` top-level page
    (page id `$NOTION_1ON1_PARENT_PAGE`)
  - Database id `$NOTION_1ON1_DB`
  - **Data source (create pages here): `$NOTION_1ON1_DS`**
  - Schema: `이름` (title), `Date` (date), `상대` (select — partner name options;
    add new options as needed). Set `상대` to the 1on1 partner. Use diarize mode.
- **Default / everything else (회의/미팅 and anything not matched above):** use the
  **Scenic `Meeting Notes` DB** (the default since 2026-06-14, in Scenic).
  - Workspace: **Scenic** (`$NOTION_WS_SCENIC`) — already pinned by default, no re-pin.
  - **Data source (create pages here): `$NOTION_SCENIC_MEETING_DS`**
  - Database id `$NOTION_SCENIC_MEETING_DB`
  - Schema: `Meeting name` (title), `Date`, `Attendees` (people), `Category` (multi_select).
- **Legacy 회의록 / default (DODO-SPACE) — only on explicit request:** use **only** when
  the user explicitly asks to route to the old DODO-SPACE DBs. Re-pin
  `NOTION_WORKSPACE_ID=$NOTION_WS_DODO` for that run.
  - 회의록: `$NOTION_MEETING_DS` (db `$NOTION_MEETING_DB`)
  - old default: `$NOTION_DEFAULT_DS` (db `$NOTION_DEFAULT_DB`)

Surface the chosen target to the user before creating the page. If the user
passes an explicit `database_id` option, that always wins over the routing rule.

**Public vs private — ALWAYS ASK before creating (user instruction, 2026-06-14).**
After routing but before building the page, ask the user whether the page should be
**퍼블릭 (team-shared)** or **프라이빗 (only me)**:
- **퍼블릭 (team-shared):** create in the routed Scenic `Meeting Notes` DB
  (`$NOTION_SCENIC_MEETING_DS`) — visible to the team. This is the normal meeting path.
- **프라이빗 (only me):** do **not** use the shared DB. Ask the user for the private
  parent (a 🔒 page only they can see) and create the page under it
  (`parent: { "page_id": <private_page_id> }`), or offer to create a new private page
  first. (1on1s already route to the private `1on1 Notes` DB and don't need this prompt.)
Surface the picked visibility + DB target together with the mode before billing.

### Transcription mode routing

Pick the transcription mode based on the title (case-insensitive).

- **diarize** — title/label contains any of: `회의록`, `회의`, `미팅`, `meeting`,
  `interview`, `인터뷰`, `1on1`, `1:1`, `원온원`. Sub-page renders `[MM:SS] Speaker X: text…`.
- **transcribe** (plain) — title/label contains any of: `강연`, `세미나`, `교육`,
  `특강`, `강의`, `lecture`, `seminar`, `talk`, `발표`. Sub-page renders flowing
  paragraphs with chunked timestamp headers.
- **default** — if neither matches and the user didn't pass `mode` explicitly,
  ask them: *"화자 분리(diarize)가 필요한 회의 녹음인가요, 아니면 화자 분리 없이
  전사만 하면 되는 강연/세미나류인가요?"*. Don't silently guess.

Always surface the picked mode to the user along with the routed DB before
spending credits.

### Shared schema (verified on both DBs)

- `Meeting name` — **title** (required; populate this with the page title)
- `Date` — date (optional; default to today's date)
- `Attendees` — people (optional; leave empty unless user supplies user IDs)
- `Category` — multi_select (optional)
- `Created by` / `Last edited by` / `Last updated time` / `생성 일시` — auto-managed

Notion's 2025+ API requires `parent: { "data_source_id": "<id>" }` when creating
pages in a multi-source database. Do not send `database_id` here.

## Preflight

Run these once at the top of the workflow and bail out with a clear message if anything is missing:

1. `[ -f "$AUDIO_FILE" ]` — file exists and is readable.
2. `ELEVENLABS_API_KEY` is set. If not, instruct the user to `export ELEVENLABS_API_KEY=...` in their shell (or run `/setup-api-key`). Never ask them to paste it in chat.
3. `command -v ntn` resolves. If missing, install with `curl -fsSL https://ntn.dev | bash` (ask first).
4. Notion auth works: `ntn doctor` reports `Token valid ✔`. The CLI accepts
   either `NOTION_API_TOKEN` *or* a stored `ntn login` session — don't require
   the env var. If `ntn doctor` shows the token is invalid, prompt the user to
   `ntn login` (it requires opening a browser). (The `Workers enabled` /
   `list workers` warnings are irrelevant — this skill only uses the Pages API.)
4.5. **Pin the workspace to Scenic (default)** (see "Workspace (pinned)" above):
   `export NOTION_WORKSPACE_ID=$NOTION_WS_SCENIC`. Do this
   before any `ntn api` call and keep it exported for every page-create/PATCH in
   this run. Confirm with `ntn api v1/users/me` → `workspace_name` = `Scenic`.
   Meetings/미팅 now create in the **Scenic** `Meeting Notes` DB by default — no re-pin.
   Re-pin to DODO-SPACE (`$NOTION_WS_DODO`) only when the user **explicitly** routes to
   the legacy DODO 회의록 / default DBs, or passes an explicit `database_id` there.
5. `command -v python3` resolves and `python3 -c 'import elevenlabs'` succeeds. If not, run `python3 -m pip install --user elevenlabs` (or `uv pip install elevenlabs`). On macOS, the system `python3` is Apple's Xcode build — `--user` install is the safe fallback.
6. `command -v ffprobe` resolves (used for duration → cost estimate; the audio itself goes straight to Scribe v2 without re-encoding). On macOS: `brew install ffmpeg`.
7. **Confirm language with the user.** Always ask: *"녹음 언어가 한국어 맞나요? (다른 언어면 알려주세요)"* — even when title looks Korean. The wrong language hint produces broken transcripts; assuming silently has burned us before. Default suggestion is `kor`. Set `LANG_HINT` accordingly.
8. **Confirm transcription mode with the user** if title doesn't clearly indicate it (see "Transcription mode routing"). Surface picked mode + DB target before billing.
8.5. **Ask public vs private before creating the page** (user instruction, 2026-06-14; see "Public vs private" under Routing). Default suggestion: 퍼블릭(team-shared) → Scenic `Meeting Notes` DB. If 프라이빗, get/create the private parent page and create under it instead. Skip for 1on1 routing (already private). Surface the picked visibility + DB target alongside the mode.
9. **For diarize mode: ask the user for the participant list before transcribing.** This is critical — pass the names as `keyterms` to Scribe v2 (most effective bias against name mishears) AND use them for `speaker_X → 실명` mapping in the merge step. Always pre-include **도현 (the user's name, per `user_name.md` memory)** as a default participant; prompt the user only for the *other* participants. Phrase: *"이 회의에 도현 외에 누가 참여하셨나요? (이름을 콤마로 구분해 알려주세요)"*. Empirically: skipping this step or relying on title-derived keyterms alone has produced repeated wrong mappings — Scribe drifts 도현 → 지훈/지은, 지운 → 두윤, 규희 → 규인 even with partial keyterms. Confirming up front saves an entire archive+rebuild cycle. Add any company/brand names mentioned in the title (e.g. 마리트, 앤트, D&C) to keyterms as well. Skip this step for plain transcribe mode (lectures don't need speaker mapping).
10. **Cost preview — show estimated cost to the user and get explicit confirmation before transcribing.** See "Cost estimation" below.

## Cost estimation

Before spending any credits, compute and surface an estimate. Get the duration once and reuse:

```bash
DUR_SEC=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$AUDIO_FILE" | cut -d. -f1)
DUR_MIN=$(awk "BEGIN { printf \"%.2f\", $DUR_SEC / 60 }")
```

Rate (point-in-time; verify in the [ElevenLabs dashboard](https://elevenlabs.io/app/usage) if a precise quote is needed — pricing varies by plan tier and can change):

| Provider   | Model       | $ / min  | $ / hour |
|------------|-------------|----------|----------|
| elevenlabs | `scribe_v2` | ~$0.0067 (≈ $0.40/hr business tier; free/creator tiers differ) | ~$0.40 |

Compute `EST_COST_USD = DUR_MIN × 0.0067`. Render with two decimals.

**Surface to the user before billing:**

```
🎙  Transcription preview
    File:     /Users/…/audio.m4a
    Duration: 64.30 min
    Model:    scribe_v2 (diarize)
    Language: kor
    Estimated cost: ~$0.43 USD
Proceed? (y/n)
```

Stash the estimate for the post-run report:

```bash
mkdir -p "$OUT_DIR"
echo "$EST_COST_USD" > "$OUT_DIR/cost_estimate.txt"
echo "$DUR_SEC" > "$OUT_DIR/duration_sec.txt"
```

If the user declines, abort cleanly — no transcription, no Notion page created.

For **long-and-expensive** previews (≥ $1.00 or audio > 60 min), repeat the cost line in bold and explicitly ask before proceeding. Never start transcription on a > 30 min file without a `y` from the user.

## Steps

### 1. Set up output dir

```bash
JOB_ID="$(basename "$AUDIO_FILE" | sed 's/\.[^.]*$//')-$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$HOME/voice-memo-to-notion-runs/$JOB_ID"
mkdir -p "$OUT_DIR"
```

### 2. Transcribe with Scribe v2 (single request)

One call handles the whole file (≤ 3 GB / 10 hr). Toggle `diarize` based on `$MODE`. Pass `keyterms` whenever the user supplied them or you've inferred obvious proper nouns from the title.

```bash
# $KEYTERMS_JSON is an optional JSON array of strings (≤100), e.g.
#   export KEYTERMS_JSON='["마이리얼트립","SUDO","Q4 OKR"]'
DIARIZE=$([ "$MODE" = "diarize" ] && echo true || echo false)

python3 - <<'PY' "$AUDIO_FILE" "$LANG_HINT" "$DIARIZE" "$OUT_DIR" "${KEYTERMS_JSON:-[]}"
import sys, os, json, time
from elevenlabs import ElevenLabs

audio, lang, diarize, out_dir, keyterms_json = sys.argv[1:6]
diarize = diarize == "true"
keyterms = json.loads(keyterms_json or "[]")

# Scribe v2 accepts ISO 639-1 or 639-3. Normalize to 639-3 for consistency.
_lang_map = {"ko": "kor", "en": "eng", "ja": "jpn", "zh": "zho"}
lang = _lang_map.get(lang, lang) if lang else None

# Hour-long files take 4–5 min server-side; the SDK's default httpx read
# timeout (~60s) raises ReadTimeout long before the result is ready. 1200s
# (20 min) covers anything up to the 10-hr cap with margin.
client = ElevenLabs(timeout=1200)
kwargs = {
    "model_id": "scribe_v2",
    "diarize": diarize,
    "timestamps_granularity": "word",
}
if lang:     kwargs["language_code"] = lang
if keyterms: kwargs["keyterms"] = keyterms

t0 = time.time()
with open(audio, "rb") as f:
    result = client.speech_to_text.convert(file=f, **kwargs)
elapsed = time.time() - t0

payload = {
    "text": getattr(result, "text", ""),
    "language_code": getattr(result, "language_code", None),
    "language_probability": getattr(result, "language_probability", None),
    "words": [
        {
            "text": w.text,
            "start": getattr(w, "start", None),
            "end": getattr(w, "end", None),
            "type": getattr(w, "type", None),
            "speaker_id": getattr(w, "speaker_id", None),
        }
        for w in (getattr(result, "words", None) or [])
    ],
    "elapsed_sec": elapsed,
}
with open(os.path.join(out_dir, "elevenlabs.raw.json"), "w") as o:
    json.dump(payload, o, ensure_ascii=False, indent=2)
print(f"scribe_v2 done in {elapsed:.1f}s — {len(payload['words'])} words, "
      f"lang={payload['language_code']} ({payload['language_probability']})")
PY
```

Notes / gotchas:
- The SDK's `with_raw_response` pattern from openai-py does NOT exist on `elevenlabs.speech_to_text.convert` in 2.47.0 — calling it raises `AttributeError`. Use the plain `.convert()` call and trace usage via the dashboard (or by timestamp) if you need request-level accounting.
- `keyterms` is the biasing knob — pass speaker names, company names, technical jargon (≤ 100 terms). This is far more effective than Whisper-style prompts.
- Audio events (laughter, applause, crowd noise) come through as words with `type=audio_event`, rendered like `[사람들 웅성거리는 소리]`. Useful context for the summary; not noise.

### 3. Merge into the renderable transcript

`elevenlabs.raw.json` already covers the whole file with absolute timestamps — no chunk-offset math needed. Group word objects into turns (diarize) or paragraphs (plain).

```python
import json, os, re
out = os.environ["OUT_DIR"]
raw = json.load(open(os.path.join(out, "elevenlabs.raw.json")))
words = raw.get("words") or []
mode = os.environ["MODE"]  # "diarize" | "transcribe"

def flush(buf, speaker, start, end):
    text = "".join(w["text"] for w in buf).strip()
    return {"start": start, "end": end, "speaker": speaker or "?", "text": text}

if mode == "diarize":
    segments, buf, cur_spk, seg_start = [], [], None, None
    for w in words:
        if w.get("type") not in ("word", "spacing"):  # skip audio_event
            continue
        spk = w.get("speaker_id") or "?"
        if cur_spk is None:
            cur_spk, seg_start = spk, w.get("start") or 0
        if spk != cur_spk and buf:
            segments.append(flush(buf, cur_spk, seg_start, buf[-1].get("end") or 0))
            buf, cur_spk, seg_start = [], spk, w.get("start") or 0
        buf.append(w)
    if buf:
        segments.append(flush(buf, cur_spk, seg_start, buf[-1].get("end") or 0))
    json.dump({"segments": segments},
              open(os.path.join(out, "merged.transcript.json"), "w"),
              ensure_ascii=False, indent=2)
else:
    text = (raw.get("text") or "").strip()
    sentences = re.split(r'(?<=[.!?。!?])\s+', text)
    paragraphs, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 > 1500:
            if buf: paragraphs.append(buf.strip())
            buf = s
        else:
            buf = (buf + " " + s) if buf else s
    if buf: paragraphs.append(buf.strip())
    # Single "chunk" spanning the whole file for downstream rendering parity.
    merged_chunks = [{"chunk": 0, "start": 0.0, "paragraphs": paragraphs}]
    json.dump({"chunks": merged_chunks},
              open(os.path.join(out, "merged.transcript.json"), "w"),
              ensure_ascii=False, indent=2)
```

Speaker IDs (`speaker_0`, `speaker_1`, …) are stable across the whole file in one pass. No per-chunk reset caveat to disclose.

### 4. Summarize

You (Claude) write the summary directly from `merged.transcript.json` (or its
flattened `.txt` form for easier reading). For long transcripts (> 25k tokens),
read the .txt in offset/limit chunks rather than splitting the file.

The output format depends on `$MODE`. For **lectures/seminars** (plain mode)
produce the rich **강연정리 / lecture write-up** format described below —
a paraphrased summary will not be enough. For **meetings** (diarize mode)
produce the meeting-minutes format described after.

#### 4a. Lecture write-up format (plain mode)

Reference exemplar: `notion.so/3252cfba780a80b0be54d4babf328593`
(호갱노노_강연정리, 197 blocks across 10 numbered sections). Match that depth.

A good 강연정리 preserves the speaker's voice and the concrete details — names,
numbers, dates, specific anecdotes — not just the abstract takeaways. A reader
who didn't attend should be able to quote it confidently. Required structure
in this order:

- **`heading_1`** — talk title (e.g. "마이리얼트립 창업 스토리 - 이동건 대표 강연 정리")
- **`quote`** — one-sentence subtitle: who spoke, where, and any constraint
  (e.g. "대전제: SNS에 공개하지 않기로 약속함")
- **`callout`** (💡 yellow_background) — the single most quotable insight
  (≤ 140 chars). Not a topic label but an actual takeaway.
- **`divider`**
- **`heading_2` 목차** + `numbered_list_item` × N — table of contents listing
  the section titles. Target 8–12 sections for an hour-long talk.
- **`divider`**
- For each section (`heading_2` "N. Title"):
  - `heading_3` sub-topics within the section
  - `bulleted_list_item` for detailed facts — preserve names, numbers, dates,
    company names, anecdote specifics (e.g. "충남 홍성 거주, 평생 해외여행 안 해본 분")
  - `numbered_list_item` for chronological sequences (creation timeline,
    decision process)
  - **`quote`** blocks for verbatim speaker lines — aim for **at least one quote
    per section** if the speaker said something memorable. These are the
    backbone of the write-up.
  - `paragraph` for short narrative explanations (1–3 sentences) when a
    bullet feels too curt
  - `divider` between sections
- **`heading_2` 📑 전사 품질 메모** — short caveat about ASR confidence,
  proper-noun mangling risk, and which `keyterms` were passed.
- **`divider`**
- Pointer paragraph to the raw transcript sub-page.

Style guidance:
- Verbatim quotes go in `quote` blocks. Paraphrased takeaways stay in bullets.
- Group quotes near the bullets they support so the reader sees claim + evidence.
- Preserve film/book/person references the speaker invoked (요다, 머니볼,
  브라이언 체스키 등) — they're part of the speaker's voice.
- Numbers, dates, company names, percentages: keep as spoken. Don't round.
- Q&A sections: each question gets its own `heading_3 "Q: ..."` with the
  answer as `quote` or `bulleted_list_item` underneath.

Length: an hour of talking typically produces 150–300 blocks in this format.
That's fine — Notion handles it (see Step 5 for >100 block batching).

#### 4b. Meeting-minutes format (diarize mode)

For meetings the deliverable is a **professional 회의록 organized as thematic
Q&A sections** — not a flat bullet summary. Synthesize the discussion the way a
skilled note-taker would: cluster by topic, rewrite the spoken back-and-forth
into clean question→answer pairs, and preserve every concrete fact. This mirrors
the bundled `meeting-minutes` reference skill — see
[references/meeting-minutes-example.md](references/meeting-minutes-example.md)
for the gold-standard depth and tone (the example is markdown; render the same
structure as Notion blocks here).

**Main page block sequence:**

- **`callout`** (💡 yellow_background) TL;DR — the single most decision-relevant
  takeaway (≤ 140 chars). An actual conclusion, not a topic label.
- **`heading_2`** "📝 요약 (Summary)" then:
  - one `paragraph` carrying meeting metadata inline — **일시 · 참석자(역할/소속) ·
    목적** — extracted from the audio/title (일시 defaults to the recording date).
  - one `paragraph`, a 2–3 sentence overview of what was discussed and concluded.
- **`heading_3`** "Key points" + `bulleted_list_item` × 3–7 — the decisions,
  open questions, and context a reader needs at a glance.
- **`heading_2`** "💬 주제별 논의 (Q&A)" — **the core of the minutes.** Cluster the
  conversation into **4–8 thematic sections ordered by logical flow, NOT
  chronologically.** Each section is a `heading_3 "N. <Topic>"` followed by
  **2–6 synthesized Q&A pairs**:
  - **Question** — a `paragraph` starting with a bold "Q. " stating the
    *underlying* question being worked through, rewritten as a clean direct
    question (not the literal words spoken). Bold the whole question line.
  - **Answer** — a `bulleted_list_item` (or `paragraph`) starting "A. " that
    fuses what was actually said. **Bold the key terms, numbers, names, and
    conclusions** inside the answer using `rich_text` segments with
    `annotations.bold=true`. Use `numbered_list_item`s for sequential
    processes/steps. One answer may span multiple bullets when it has distinct
    parts (e.g. the founder's answer + the investor's pushback).
  - Close with a `heading_3 "N. 기타"` section for anything that didn't cluster.
- **`heading_2`** "✅ Action Plan" — **REQUIRED for 회의록 routing**, and
  recommended whenever the meeting produced concrete next steps. A list of
  `to_do` blocks — one per concrete action item pulled from the transcript.
  Each item should include: the owner (if stated), the task itself, and a
  deadline in parentheses when the recording mentions one (e.g. "next week",
  "within 2 weeks"). Convert relative deadlines to absolute dates using the
  recording date. Do NOT invent owners or deadlines that weren't spoken;
  leave them off instead. Group by owner when there are 3+ items for the same
  person.
- **`heading_3`** "Speakers" + `bulleted_list_item` × N — list each
  `speaker_X` with a one-line description of who they appear to be. **When the
  user supplied a participant list (Preflight #9), map to the real name** —
  e.g. "speaker_0 — 박도현(도현): 창업자, 제품 피칭", "speaker_1 — 영무: 투자 심사역".
- **`heading_3`** "전사 품질 메모" + caveat paragraph — ASR confidence,
  proper-noun mishears (and their likely correct form), keyterms passed, and the
  source of the speaker→name mapping (user-confirmed vs inferred).
- `divider` + pointer to raw transcript sub-page.

**Synthesis rules (from the `meeting-minutes` reference — apply all):**

- **Synthesize, don't transcribe.** Questions capture intent; answers fuse the
  transcript's facts. Strip speech artifacts ("어…", "음…", "그러니까", "네/맞아요"
  agreement markers, stray English fragments).
- **Cluster by theme, order by logic** — 4–8 sections following the argument,
  not the call's timeline.
- **Preserve hard facts** — numbers, dates, amounts, product/people/company
  names, decisions, action items, and nuanced distinctions ("X works but Y
  doesn't because…"). Never round or drop a figure.
- **Exclude** side chatter, jokes, repetition, and filler.
- **Bold** key terms / figures / conclusions inside answers so the page stays
  skimmable (Notion `rich_text` `annotations.bold=true`).

Match the summary language to the audio language. Korean audio → Korean minutes.

### 5. Build the page payload

Schema is known — no discovery needed. Defaults:

- `parent`: picked by the Routing rule above. **Default (퍼블릭 meeting):**
  `{ "data_source_id": "$NOTION_SCENIC_MEETING_DS" }` (Scenic Meeting Notes).
  **프라이빗:** `{ "page_id": "<private_parent_page_id>" }` instead.
  **Legacy DODO (explicit only):** `$NOTION_MEETING_DS` / `$NOTION_DEFAULT_DS`.
  Override with the `database_id` option when supplied.
- `properties.Meeting name.title[0].text.content`: page title (audio filename without ext, or user override)
- `properties.Date.date.start`: today's date in `YYYY-MM-DD` (use `date +%F`)

If the user later renames the title property or moves a database, refresh both
the data_source_id and the title prop name in this skill (and re-verify with
`ntn api v1/data_sources/<id>`).

**Main page block sequence:** see Step 4 — the structure differs for lectures
(4a, 강연정리 format ~150–300 blocks) vs meetings (4b, thematic Q&A minutes
~40–80 blocks; a ~35-min meeting with 8–13 Q&A pairs lands around 60–65 blocks).
Build the `children` array following whichever applies. The 100-block-per-POST
cap (see Step 6) applies to rich 4b minutes too — chunk + PATCH if you exceed it.

The raw transcript does NOT go on the main page in either case. It lives in a
sub-page so the main page stays scannable — drafts, sharing, and linking all
become cleaner.

**Sub-page: "원문 전사 / Raw Transcript"**

A child page is created after the main page is created (Step 6). The
structure differs by mode:

- **Diarize mode:**
  1. `paragraph` blocks — one per speaker turn from `merged.segments`
     (format: `[MM:SS] Speaker X: text…`)

- **Plain transcribe mode (lectures):**
  1. `paragraph` blocks — one per pre-split paragraph from `merged.chunks[0].paragraphs`
     (no speaker prefix, no per-paragraph timestamp; the file is one continuous
     pass so timestamps mid-text rarely help the reader).

**Notion API limits — respect these or the request 400s:**

- Each `rich_text.text.content` ≤ 2000 chars. Split long segments across
  multiple `rich_text` array entries within the same paragraph block.
- ≤ 100 child blocks per single request. If the transcript exceeds this, send
  the first 100 in the sub-page's create call and `PATCH` the rest in batches
  of ≤ 100 to `v1/blocks/<sub_page_id>/children`.
- ≤ 100 nesting levels (not a concern here — we stay flat).
- `child_page` blocks cannot be created directly in a `children` array. To
  create a sub-page you POST to `v1/pages` with `parent: {page_id: <parent>}`.

### 6. Create the main page, then the transcript sub-page

Two-phase create — the raw transcript lives in a sub-page so the main page
stays scannable.

**Phase 1 — main page (summary-only, short):**

```bash
ntn api v1/pages -d @main_payload.json
```

Payload shape:
```json
{
  "parent": {"data_source_id": "<DATA_SOURCE_ID>"},
  "properties": {
    "Meeting name": {"title": [{"text": {"content": "<TITLE>"}}]},
    "Date": {"date": {"start": "<YYYY-MM-DD>"}}
  },
  "children": [ /* first ≤ 100 blocks — see batching note below */ ]
}
```

Capture `.id` as `MAIN_PAGE_ID` and `.url` for the final report.

**Multi-chunk POST + PATCH (required for the lecture 강연정리 format; also for
long 4b Q&A minutes that exceed 100 blocks):**
The 100-block-per-request cap applies to `POST /v1/pages` too, not just to
sub-page batching. A 강연정리 main page typically runs 150–300 blocks. Split
the block list into ≤100-block chunks, POST the first chunk with the page
metadata, then PATCH each remaining chunk to `v1/blocks/<MAIN_PAGE_ID>/children`:

```bash
ntn api "v1/blocks/$MAIN_PAGE_ID/children" -X PATCH -d @main_extra_2.json
ntn api "v1/blocks/$MAIN_PAGE_ID/children" -X PATCH -d @main_extra_3.json
# ... one PATCH per additional chunk
```

Notion appends in order — PATCH preserves insertion order — so the page reads
top-to-bottom exactly as your chunked list would. Verify with the response's
`results.length` matching what you sent.

**Phase 2 — "원문 전사" sub-page under the main page:**

```bash
ntn api v1/pages -d @subpage_payload.json
```

Payload shape (note: `parent.page_id`, not `data_source_id`):
```json
{
  "parent": {"page_id": "<MAIN_PAGE_ID>"},
  "properties": {
    "title": {"title": [{"text": {"content": "원문 전사 / Raw Transcript"}}]}
  },
  "children": [ /* up to 100 transcript blocks */ ]
}
```

Pages created under a page parent use the literal key `title` (not the DB's
title property name) because they aren't database rows.

Capture the sub-page `.id` as `SUB_PAGE_ID`. If the transcript has more than
~100 blocks (likely for hour-long recordings), append the remainder in batches
of ≤ 100:

```bash
ntn api "v1/blocks/$SUB_PAGE_ID/children" -X PATCH -d @batch.json
```

Notion automatically renders the sub-page as a clickable child_page block on
the main page — no extra linking needed.

### 7. Report back

Compute the **actual** cost from the audio duration we already saved during preflight (`$OUT_DIR/duration_sec.txt`). The ElevenLabs API doesn't return a billed-cost field in-band, so this is a deterministic recompute against the rate table — surface it next to the dashboard URL so the user can cross-check.

```bash
DUR_SEC=$(cat "$OUT_DIR/duration_sec.txt")
DUR_MIN=$(awk "BEGIN { printf \"%.2f\", $DUR_SEC / 60 }")
RATE_PER_MIN=0.0067
ACTUAL_COST=$(awk "BEGIN { printf \"%.3f\", $DUR_MIN * $RATE_PER_MIN }")
EST=$(cat "$OUT_DIR/cost_estimate.txt")
echo "💸 Actual transcription cost: \$$ACTUAL_COST USD ($DUR_MIN min × \$$RATE_PER_MIN/min) — estimated \$$EST"
echo "    Verify in dashboard: https://elevenlabs.io/app/usage"
```

Then print:
- The Notion page URL (clickable).
- Path to the saved local transcript JSON (so the user has a backup).
- Mode used (diarize vs plain) and any keyterms passed.
- The actual cost line above.

If the actual cost differs from the estimate by > 20 %, call it out — usually means the rate constant in this skill is stale and should be updated.

## Failure handling

- ElevenLabs 401 → API key invalid; instruct the user to refresh `ELEVENLABS_API_KEY`.
- ElevenLabs 422 → invalid parameters (most often a bad `language_code` or an unsupported audio container). Surface the exact error.
- ElevenLabs 429 → rate limited; back off and retry once with jitter.
- Notion 401/403 → token is missing/invalid; instruct the user to refresh `NOTION_API_TOKEN`.
- Notion 404 on the database → the integration may not be shared with that database. Tell the user to share the page/database with their integration in the Notion UI.
- Notion 400 with `body.children.length` → batching logic broke; reduce batch size and retry the failed batch only.

## Notes

- Keep the saved JSON transcript under `~/voice-memo-to-notion-runs/<job-id>/`. Don't delete it after upload — useful if the Notion create fails partway and needs to be retried without re-billing ElevenLabs.
- Don't echo `ELEVENLABS_API_KEY` or `NOTION_API_TOKEN` in any logs.
- The default DB lives in `$NOTION_USER`'s workspace; if the user is in a different workspace, the integration must be installed there too.

## Lessons learned (empirical, fold into changes)

- **Scribe v2 is the only transcription path now.** Earlier versions of this skill supported OpenAI's `gpt-4o-transcribe(-diarize)`. We removed it after a head-to-head on a 15-min Korean lecture (`마이리얼트립`): same price point (~$0.09 vs $0.10), but OpenAI dropped content, fragmented utterances heavily, emitted `###` segment markers, and — worst — bled the biasing prompt straight into the output. Scribe v2 produced clean flowing text, caught audio events (`[사람들 웅성거리는 소리]`), and rendered numerals the way the speaker actually said them.
- **Always confirm language with the user before transcribing.** Even if title looks Korean, ask once. Wrong language hint silently produces broken transcripts. Default suggestion: `kor`.
- **Always show cost preview *and* request confirmation before billing.** Even at ~$0.40/hr Scribe v2 it's real money on longer files. The post-run "actual cost" line is a deterministic recompute from duration × rate — the API doesn't return a billed amount in-band, so the dashboard remains source-of-truth for invoices.
- **`with_raw_response` doesn't exist on `client.speech_to_text.convert` in elevenlabs SDK 2.47.0.** The openai-py pattern (`client.foo.with_raw_response.bar(...)`) does not transfer. Call `.convert()` directly. If you need request-level accounting, look up by timestamp in the dashboard.
- **Always construct the client as `ElevenLabs(timeout=1200)`.** The SDK defaults to httpx's short read timeout (~60 s). Scribe v2 takes ~4–5 min server-side for a 60-min Korean lecture, so the default raises `httpx.ReadTimeout` long before the result is ready. 1200 s (20 min) covers anything up to the 10-hr cap with margin. Burned on the first 마이리얼트립 강연 run; fix is one keyword arg.
- **Notion page archival uses `in_trash: true`, not `archived: true`** in the 2025+ API. Sending `archived` returns `400 body failed validation: body.archived should be not present`. The response field is also `in_trash`; `archived` reads as `None`. Same behavior — archiving a parent also makes children inaccessible — so recreate sub-pages after archiving a main page.
- **Notion's 100-block-per-request cap applies to `POST /v1/pages` too**, not just to `PATCH /v1/blocks/<id>/children`. The lecture 강연정리 format runs 150–300 blocks for an hour-long talk; chunk into ≤100-block groups, POST the first with metadata, PATCH the rest in order. PATCH preserves insertion order so the page reads top-to-bottom as the chunked list does.
- **For long transcripts, don't try to `Read` the .txt or merged.json in one shot.** Tokens exceed the 25k Read cap. Either split into ~10k-char `part_NN.txt` files via a Python helper and read each in parallel, or use `Read` with explicit `offset`/`limit`.
- **The lecture 강연정리 format is a hard-deliverable, not a stretch goal.** Paraphrased-bullets summaries fall flat compared to the reference (호갱노노_강연정리, 3252cfba…). Hit ~10 numbered sections with TOC + verbatim `quote` blocks + preserved names/numbers — see Step 4a.
- **The 4b meeting format is thematic Q&A, not a flat bullet list.** Adopted from the bundled `meeting-minutes` reference skill (see `references/meeting-minutes-example.md`). Cluster the call into 4–8 topic sections ordered by logic (not chronology), rewrite each exchange into a synthesized `Q.`→`A.` pair, and bold the facts. Real run: the 카카오벤처스 Scenic 프리시드 미팅 (35 min, 2 speakers) produced a clean 13-pair "💬 주제별 논의 (Q&A)" section that the user specifically asked for after the first flat summary — bake it in from the start. Insert the Q&A section between "Open questions" and "✅ Action Plan"; if added to an existing page, use positional `after` with `--notion-version 2022-06-28`.
- **Use the participant list to map `speaker_X → 실명` and surface the mapping for confirmation when ambiguous.** When two speakers both use "저희"/role-neutral language (founder + investor in a pitch meeting), the role isn't decidable from text alone — ask the user which voice did what (e.g. "who pitched vs who asked the evaluation questions?") before rendering. Confirmed once, render real names everywhere (summary, Speakers, raw transcript). Scenic run: speaker_0 was confirmed as 박도현, speaker_1 as 영무 this way.
- **Fix obvious product/brand mishears in the summary, but leave the raw transcript faithful.** Scribe rendered the product name "Scenic" as "SEMY/세미" throughout. Use the correct name in the minutes and add a "⚠ 'Scenic' ↔ 'SEMY/세미' mishear" note in 전사 품질 메모; keep the sub-page transcript as Scribe produced it (offer a find-replace only if the user asks).
- **For diarize mode, ask for the participant list before transcribing.** Empirical pattern: across two consecutive meeting runs we had to archive+rebuild the Notion page after the user corrected the speaker names. Title-derived keyterms alone don't lock the ASR — Scribe drifts 도현 → 지훈/지은, 지운 → 두윤, 규희 → 규인 even with partial keyterms. Asking up front (with 도현 pre-included) gives both the keyterms and the `speaker_X → 실명` mapping for the merge step. See Preflight #9.
- **Scribe v2 occasionally splits one speaker into two labels** during brief audio-quality changes (mic distance, seating shift). Symptom: a label appears only during a short window (e.g. 18:35~24:23, 6% of total) with content that flows naturally from another label's adjacent turns. Recognize and merge before rendering — don't create a phantom 4th participant. The participant list from Preflight #9 makes this much easier to catch.
- **`keyterms` >> `prompt`.** Up to 100 names/terms can be passed and they actually bias the recognizer toward those tokens. Always pass at least the topic/company name when you can infer it from the title (e.g. `keyterms=["마이리얼트립"]` for a `마이리얼트립 강연` recording).
- **Mac-stock python3 lacks `elevenlabs`:** install with `python3 -m pip install --user elevenlabs`. The `--user` script dir (`~/Library/Python/3.9/bin`) isn't on PATH but that doesn't matter — we invoke via `python3 -c`/heredoc.
- **Notion 2025+ DBs use data sources:** the Pages API requires `parent.data_source_id`, not `parent.database_id`, when the DB has a `data_sources[]` array. The legacy form silently fails or routes to the wrong place. The skill's hard-coded data source ID handles this.
- **Notion CLI accepts stored login (`ntn login`) without `NOTION_API_TOKEN`:** the env var is only needed to override. Don't gate on its presence.
- **`ntn api` reads the body from stdin, not `-d @file`:** pass JSON via `cat payload.json | ntn api v1/pages -X POST`. The `-d` flag only accepts an inline JSON string.
- **Inserting blocks mid-page (`after` field) requires the 2022-06-28 Notion version:** the current default rejects `after` on `PATCH v1/blocks/<id>/children`. Use `--notion-version 2022-06-28` when you need positional insertion (e.g. adding an Action Plan into an existing page).
- **Voice Memos titles live in `ZENCRYPTEDTITLE`, not `ZCUSTOMLABEL`:** despite the name, the value reads as plaintext through SQLite. `ZCUSTOMLABEL` is usually a default ISO timestamp.
- **Default is now Scenic, not DODO-SPACE (changed 2026-06-14).** Meetings/미팅/everything
  else create in the **Scenic `Meeting Notes` DB** (`$NOTION_SCENIC_MEETING_DS`, db
  `$NOTION_SCENIC_MEETING_DB`) under the default Scenic pin — no re-pin. On the Aow 작가님
  미팅 run the page was first (wrongly) created in DODO-SPACE; the user asked to make Scenic
  the standing default and to **always ask 퍼블릭(team-shared) vs 프라이빗(only-me)** before
  creating. The legacy DODO 회의록/default DBs (`$NOTION_MEETING_DS` / `$NOTION_DEFAULT_DS`)
  are now used **only on explicit request** — and only then re-pin
  `NOTION_WORKSPACE_ID=$NOTION_WS_DODO` for that run.
- **The `ntn` default workspace is not stable — always pin explicitly.** `ntn` persists the
  last-used `NOTION_WORKSPACE_ID` into `~/.config/notion/config.json` →
  `defaultWorkspaceIds.prod`, so a prior run can drift the default and make every `ntn api`
  call 404 (`Could not find data_source`) because the data-source id is invisible from the
  wrong workspace. Export the intended `NOTION_WORKSPACE_ID` at the top of the run, keep it
  exported for every create/PATCH, and verify with `ntn api v1/users/me`.
- **Moving a page between workspaces = recreate + trash, not edit.** A page can't be reparented
  across workspaces via the API. To move it: rebuild the payloads pointing at the new
  data_source/parent, POST the new page (+sub-page batches), then archive the old one with
  `{"in_trash": true}` (not `archived`). On the Aow run this moved the note DODO→Scenic cleanly.
- **Avoid heredocs inside the skill's bash steps when the harness may auto-background the call.**
  A backgrounded `bash` with inline `<<'PY'` heredocs silently stalled mid-script (only the first
  line printed) on the Aow run. Prefer a written `.sh` file run with `bash file.sh`, or `python3 -c`
  one-liners, and write results/IDs to a file you can read back.
