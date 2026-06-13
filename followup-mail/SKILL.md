---
name: followup-mail
description: "Draft a meeting follow-up email (Korean) and save it as a Gmail draft — never sends. Use when the user asks to write a 팔로업 메일 / follow-up email after a meeting, or mentions 미팅 팔로업, 후속 메일, follow-up draft."
metadata:
  version: 1.1.0
  openclaw:
    category: "productivity"
    requires:
      bins:
        - gws
---

# Follow-up Email Drafter

Generates a meeting follow-up email in the established format (sent by `$FOLLOWUP_FROM_NAME`) and saves it as a **Gmail draft** (it never sends). The user reviews and sends manually from Gmail.

> **PREREQUISITE:** `gws` CLI authenticated. If `gws` calls fail with auth/keyring errors, see `../gws-shared/SKILL.md`.

## Config

Personal values live in the repo `.env`, not here. Load them before saving the draft:

```bash
set -a; source ~/Developer/dodo-skills/.env; set +a
```

- `FOLLOWUP_FROM_NAME` — signature name (e.g. 박도현).
- `FOLLOWUP_TO` — default recipient when the user doesn't name one.
- `FOLLOWUP_SUBJECT_TAG` — subject prefix, rendered as `[$FOLLOWUP_SUBJECT_TAG]`.

If a var is unset, ask the user for the value instead of guessing.

## When to use

The user wants a follow-up email after a meeting — phrases like "팔로업 메일 써줘", "미팅 후속 메일 초안", "follow-up draft", "{이름}님한테 팔로업 보내야 해".

## Workflow

### 1. Gather the inputs

Ask for whatever is missing (gather concisely, don't over-interrogate):

| Input | Required | Notes |
|-------|----------|-------|
| 받는 사람 이름 | ✓ | e.g. 한솔, 이나 → used as `{이름}님 안녕하세요,` |
| 받는 사람 이메일 | — | default `$FOLLOWUP_TO`; override only if the user names a different recipient |
| 미팅 성격 / 제목 키워드 | ✓ | shapes subject, e.g. "미팅", "금일 미팅 내용 정리" |
| 개인화 코멘트 | ✓ | one warm sentence about their work/the meeting |
| 본론 섹션 2~3개 | ✓ | each = 굵은 소제목 + 불릿 핵심 내용 |
| Next Step + 데드라인 | ✓ | concrete ask + 날짜/회신 요청 |
| Cc | — | none by default; only add if the user explicitly asks |

If the user gives raw meeting notes, infer the sections yourself and confirm the draft before saving.

### 2. Build the body

Fill `TEMPLATE.md` in this directory. Hard rules:

- 정중한 존댓말, 따뜻하지만 비즈니스 톤.
- Numbered bold section headers: `*1/ {제목}*`, `*2/ {제목}*` … (2~3개).
- Bullets with `-` under each section, scannable.
- **마지막 섹션은 항상 Next Step** — 명확한 요청 + 데드라인(예: "다음 주 수요일까지", "가능하신 시간대 2~3개 회신").
- Always close with:
  ```
  감사합니다,
  {$FOLLOWUP_FROM_NAME} 드림
  ```

### 3. Subject line

```
[{$FOLLOWUP_SUBJECT_TAG}] {미팅 성격} 팔로업
```
e.g. `[Scenic] 미팅 팔로업`, `[Scenic] 금일 미팅 내용 정리 및 팔로업`

### 4. Show the draft, then save (do NOT send)

Print the full subject + body for the user to review. After they confirm, save as a Gmail draft:

```bash
gws gmail +send \
  --to "$FOLLOWUP_TO" \
  --subject "[$FOLLOWUP_SUBJECT_TAG] {미팅성격} 팔로업" \
  --body "{본문}" \
  --draft
```

> `--to` 기본값은 `$FOLLOWUP_TO`. 사용자가 다른 수신자를 지정하면 그 값으로 교체.
> Cc는 기본으로 넣지 않음. 사용자가 명시적으로 요청할 때만 `--cc` 추가.

- `--draft` is **mandatory** — this skill never sends.
- Confirm the draft was created and tell the user it's waiting in Gmail → Drafts for review.

> [!CAUTION]
> Never run `+send` without `--draft`. Never call `drafts.send`. This skill only prepares; the user sends.

## See Also
- [TEMPLATE.md](./TEMPLATE.md) — fill-in-the-blank body template
- [gws-gmail-send](../gws-gmail-send/SKILL.md) — underlying send/draft command
