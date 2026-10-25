---
name: client-call-debrief
description: "Turn a B2B client/sales call recording into a debrief: ElevenLabs Scribe v2 diarized transcript, Korean meeting minutes, the client's psychological hurdles (with quoted evidence), deal temperature, prioritized follow-up actions, and a follow-up message draft (never sent). Saves summary + transcript notes to the Obsidian vault (50 Meetings). Use when the user hands over a client call recording and says 통화 녹음 정리해줘, 클라이언트 통화 분석, 세일즈 콜 디브리프, 고객 허들 찾아줘, 후속 액션 정해줘, 'debrief this sales call', or similar."
metadata:
  version: 1.0.0
---

# Client Call Debrief

Takes a recording of a call between the user (selling) and a B2B client, and produces one
Obsidian note that answers three questions:

1. **What was said?** — meeting minutes as thematic Q&A, plus both sides' commitments.
2. **What is stopping the client from saying yes?** — psychological hurdles, each with a quoted,
   timestamped piece of evidence, an evidence level, and a question to check it next time.
3. **What do we do next?** — prioritized follow-up actions tied to those hurdles, and one
   follow-up message draft.

Transcription is ElevenLabs Scribe v2 (same engine as `voice-memo-2-meeting-note`). Everything
after transcription is your own reading of the transcript, guided by
[references/hurdle-taxonomy.md](references/hurdle-taxonomy.md) and laid out per
[references/debrief-template.md](references/debrief-template.md).

## Scripts

| Script | What it does | Costs money |
|---|---|---|
| `scripts/transcribe.py` | Copies the audio into the run folder, calls Scribe v2 with diarization, writes `raw.json`, `transcript.json`, `meta.json` | Yes (≈ $0.40/hr, +20% with keyterms, +10% with `--roles`) |
| `scripts/analyze_call.py` | Applies real names, writes `transcript.md`, and computes call signals (`signals.json`, `signals.md`): talk share, longest turns, question counts, client response delays, hurdle cue words in the client's lines | No — rerun freely |

Both print Korean status lines. Run them with `python3 <skill_dir>/scripts/<name>.py`.

## Preflight

Each Bash tool call starts a fresh shell, so variables don't carry over. Resolve the values below
once, then write the **literal paths** into every later command. `$SKILL_DIR`, `$OBSIDIAN_VAULT`
and `$RUN` in the snippets below stand for those literal paths.

1. Resolve the skill dir and the vault path from the repo `.env`:
   ```bash
   SKILL_DIR="$(readlink ~/.claude/skills/client-call-debrief || echo ~/.claude/skills/client-call-debrief)"
   set -a; source "$(dirname "$SKILL_DIR")/.env" 2>/dev/null; set +a
   echo "SKILL_DIR=$SKILL_DIR"; echo "OBSIDIAN_VAULT=$OBSIDIAN_VAULT"
   ```
   `OBSIDIAN_VAULT` must point at the vault root. If it is empty, ask the user for the vault path
   and suggest adding `OBSIDIAN_VAULT="..."` to the repo `.env`.
2. The audio file exists. Recordings from iCloud folders (Desktop, Documents) may be dataless
   placeholders. `transcribe.py` copies the file first, which downloads it.
   If the user points at Apple Voice Memos instead of a file, find it with:
   ```bash
   VM="$HOME/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
   sqlite3 -separator $'\t' "$VM/CloudRecordings.db" \
     "SELECT ZENCRYPTEDTITLE, ZPATH, ZDURATION, date(ZDATE + 978307200, 'unixepoch', 'localtime')
      FROM ZCLOUDRECORDING ORDER BY ZDATE DESC LIMIT 5;"
   ```
   (needs Full Disk Access; the file is `$VM/<ZPATH>`). iPhone call recordings live in the Notes app.
   Ask the user to share the audio to Files first.
3. `ELEVENLABS_API_KEY` is set in the shell. Never ask for it in chat or echo it.
4. `python3 -c 'import elevenlabs'` works. If not: `python3 -m pip install --user elevenlabs`.
   `ffprobe` is optional (used only for the pre-run cost estimate).

## Step 1 — Intake (one message)

Ask only for what the user's request didn't already give, in a single message:

- **고객사와 상대방** — company, name, title. These become keyterms, the speaker names, and the filename.
- **우리 쪽 참석자** — default is the user alone (`$FOLLOWUP_FROM_NAME`, else 도현).
- **맥락** (optional but valuable) — deal stage (첫 상담 / 제안 후 / 협상 / 계약 직전 / 계약 후), what was
  offered and at what price, anything the client said before this call.
- **언어** — confirm Korean (`kor`) even when it looks obvious. A wrong language hint silently
  ruins the transcript.

Call date = the date the user gives, else the file's creation date
(`stat -f %SB -t %F "<file>"`), else its mtime. Never today's date by default.

Then look for earlier debriefs with the same client:

```bash
grep -l "^company: <고객사>" "$OBSIDIAN_VAULT/50 Meetings/"*.md 2>/dev/null
```

If there are any, read the latest one's 허들 and 후속 액션 sections. You will compare against them in Step 6.

## Step 2 — Transcribe

Pick the run folder once, as a literal path, and reuse it in every later step:
`$HOME/client-call-debrief-runs/<YYYY-MM-DD>-<고객사>-<HHMMSS now>`. Don't rebuild it
with `$(date …)` in a later command, because that points at a new, empty folder.

```bash
python3 "$SKILL_DIR/scripts/transcribe.py" "<audio>" --out-dir "$RUN" \
  --lang kor --speakers <N> --keyterms "<고객사>,<상대방 이름>,<제품명>,<우리 회사명>" [--roles]
```

- `--speakers` = total people on the call. It is an upper bound that helps diarization.
- `--roles` (2-person calls only) makes Scribe label the speakers `agent` and `customer`
  instead of `speaker_0/1`. Use it for every 1:1 call. It costs 10% more and saves a mapping step.
- Keyterms: names, company, product, and jargon the client used. Each must be under 50 characters,
  with no `<>{}[]\`.
- The script prints the estimated cost before calling. Don't ask for cost confirmation. Report it
  at the end.

## Step 3 — Map speakers

Read the first ~10 turns of `$RUN/transcript.json`.

- With `--roles`: `agent` is normally the user (the one proposing, explaining the offer). Check this
  against the content. If the client was pitching to the user, the labels are reversed.
- Without `--roles`: map `speaker_N` to people by content (who introduces the offer, who describes
  their business). If two speakers sound role-neutral, ask the user before going further.
- Scribe sometimes splits one person into two labels for a short stretch, for example a label
  that appears only in one short window and continues another label's sentence. Map both labels
  to the same name. Pass `--me` for each label on our side.

```bash
python3 "$SKILL_DIR/scripts/analyze_call.py" "$RUN" --me agent \
  --name agent=도현 --name customer="김OO 대표"
```

`--me` defaults to `agent` when the transcript has role labels. Otherwise it is required.

## Step 4 — Read everything

Read `$RUN/transcript.md` in full. For long calls (> ~25k tokens), read it with offset/limit in
parts, never just the beginning. Then read `$RUN/signals.md` and the `low_confidence` list in
`$RUN/meta.json`: words with logprob below -0.5, usually misheard names. An empty list means
Scribe was confident throughout.

The signals are pointers, not findings. Go to every client response delay ≥ 3 s and every cue
word, read what came before and after, and decide what it actually was. `signals.md` shows the
10 longest delays and the first 40 cues. The full lists are in `signals.json`.

Timestamps are `[MM:SS]`, or `[H:MM:SS]` past the first hour. Quote them as the scripts print them.

## Step 5 — Meeting minutes

Write the 📝 회의록 section per the template:

- 3–6 topics in logical order (현황 → 니즈 → 제안 → 조건 → 다음 단계), not the call's timeline.
- Each topic: synthesized **Q.** (the underlying question, cleanly worded) → **A.** (what was actually
  said, merged). Strip fillers. Keep every number, amount, date, and name as spoken. Bold key facts.
- 약속 사항: what each side said they would do. If the call ended without a concrete next step,
  write "합의된 다음 단계 없음". That is a finding, not a gap to paper over.

## Step 6 — Hurdles, buying signals, deal temperature

Follow [references/hurdle-taxonomy.md](references/hurdle-taxonomy.md). For each hurdle:

- type, strength (상/중/하), evidence level (명시/신호/추정)
- the client's exact words with `[MM:SS]`, plus any signal (a 3.9 s silence right after the price,
  "글쎄요", a topic change)
- surface → root hypothesis, what is still unknown, one 검증 질문, and a 해소 방향

Rules that matter most:

- Separate surface from root. "비싸요" plus "효과가 있을지 모르겠어요" is usually **one** root
  hurdle (효과·확신) showing up as price.
- Only `명시`/`신호` hurdles may drive actions on their own. `추정` hurdles go to "다음 통화에서 물어볼 것".
- Also record buying signals. A list of hurdles alone skews the deal temperature.
- Deal temperature is 🟢/🟡/🔴 by the taxonomy's definitions, with a 1–2 sentence reason.
- If there is a previous debrief, fill 이전 통화 대비: which hurdles were resolved, which persist,
  which past actions were done.
- Don't diagnose personality or emotions. Describe the decision barrier, not the person.

## Step 7 — Actions, message draft, self-feedback

**후속 액션** — 3–6 checkboxes, highest priority first:
- Commitments the user made on the call come first (e.g. "사례 자료 오늘 메일").
- Every action names the hurdle it addresses `(→ H1)` or the commitment it fulfills.
- Owner, absolute date (computed from the call date), channel.
- Exactly one action secures the next contact (who, when, about what), with a concrete date if
  the call didn't produce one.
- Don't invent owners, deadlines, case studies, or numbers the user doesn't have. If a hurdle
  needs material that may not exist (a case study, an ROI calculation), the action is to
  prepare it.

**후속 메시지 초안** — one message in the channel the call implied (mail or KakaoTalk): thanks →
what was promised → acknowledge the client's own stated concern and answer it → one concrete next
step with two time options. Korean 존댓말, short. No fake deadlines, scarcity, or pressure.
**Never send it.** Offer to save a mail version as a Gmail draft with the `followup-mail` skill.

**셀프 피드백** — one thing the user did well and two to change, each with a timestamp. Include an
alternative line the user could have said. Typical targets: talking over a hesitation, answering a
concern with a pitch instead of a question, no next step proposed, talk share > 65%.

## Step 8 — Save to Obsidian

Write the summary note per [references/debrief-template.md](references/debrief-template.md), plus a
transcript note. [references/example-debrief.md](references/example-debrief.md) is a finished
example. Match its depth.

First choose one base name, `BASE = <YYYY-MM-DD> <고객사> 통화`. If either `BASE.md` or
`BASE (전사).md` already exists in `50 Meetings/`, use `<YYYY-MM-DD> <고객사> 통화 (2)` (then `(3)`, …)
as `BASE`. Never overwrite a note. Use the same `BASE` for both files and both links:

```
$OBSIDIAN_VAULT/50 Meetings/<BASE>.md          # debrief, with frontmatter
$OBSIDIAN_VAULT/50 Meetings/<BASE> (전사).md   # transcript
```

- Transcript note = a backlink line `← 디브리프: [[<BASE>]]`, a blank line, then `$RUN/transcript.md`
  as is. Keep it faithful to Scribe. Fix misheard names only in the debrief and list them in
  전사 품질 메모.
- The debrief's last line is `→ 원문 전사: [[<BASE> (전사)]]`.
- Paste `$RUN/signals.md` into 📊 통화 지표.
- Keep copies in `$RUN` as `debrief.md`.
- The vault is a git repo. Don't commit.

## Step 9 — Report

Tell the user, briefly: deal temperature and the top hurdle, the first action due, both note
paths, the run folder, and the transcription cost from `meta.json` (`cost_usd`). Point to
https://elevenlabs.io/app/usage for the billed amount. Then offer the Gmail draft.

## Failure handling

- Scribe 401: the key is invalid. Tell the user to refresh `ELEVENLABS_API_KEY`.
- Scribe 422: usually a bad `language_code` or an unsupported container. Show the error. Convert with
  `ffmpeg -i in -ac 1 -ar 16000 out.wav` and retry.
- Scribe 429: wait a few seconds and retry once.
- Transcript with only one speaker on a two-person call: the call was probably recorded from one
  side only (common with phone recorders), or the voices are very similar. Tell the user and rerun
  once without `--roles`. If it is still one speaker, the call signals are meaningless: run
  `analyze_call.py --me <that id>` only to get `transcript.md`, leave 📊 통화 지표 as "화자 분리 실패로 산출 불가",
  attribute lines to people by content while writing, and mark every attribution as 추정 in
  전사 품질 메모. Turns still break at pauses, so each line keeps its own timestamp.
- `transcribe.py` exits non-zero with "전사된 문장이 없어요" when Scribe returns no words. Check the
  language hint and that the file actually contains speech.
- Keep `$RUN` after a failure. `analyze_call.py` and the note can be redone without paying for
  transcription again.

## Notes

- Client calls contain third-party personal data. Don't copy phone numbers, emails, or other
  contact details from the transcript into the debrief unless the user asks.
- The cue word list lives in `CUES` at the top of `scripts/analyze_call.py`. Add terms the user's
  clients actually use. False positives are fine because every cue gets read in context.
- Tests: `python3 -m unittest discover -s client-call-debrief/tests` from the repo root (no API calls).
