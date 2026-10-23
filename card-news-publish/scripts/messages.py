"""컨펌 메시지(Block Kit) 구성. Slack 호출 없이 덱 정보로 블록만 만든다."""

LABELS = {"instagram": "인스타그램", "threads": "스레드"}
CAPTION_TITLES = {"instagram": ":memo: *인스타그램 캡션*", "threads": ":thread: *스레드 본문*"}


def action_value(deck):
    return f"{deck['slug']}:v2"  # 콜론이 없는 값은 확인창·캡션이 없던 이전 버전 메시지


def platforms_label(deck):
    return "·".join(LABELS[p] for p in LABELS if p in deck["captions"])


def quote(text):
    return "\n".join(">" + line for line in text.split("\n"))


def fallback_text(deck, prefix="카드뉴스 발행 컨펌 요청"):
    return f"{prefix}: {deck['title']} — 피그마: <{deck['figma_url']}>"


def build_blocks(deck, owner, file_id=None, status=None):
    n = len(deck["slides"])
    context = f"{n}장 · {deck['meta']}" if deck.get("meta") else f"{n}장"
    if deck.get("warning"):
        context += f"\n:warning: {deck['warning']}"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": ":newspaper: 카드뉴스 발행 컨펌 요청", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{deck['title']}*" + (f"\n{deck['summary']}" if deck.get("summary") else "")}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f":art: *피그마 링크:* <{deck['figma_url']}|{deck.get('figma_label', deck['title'])} ({n}장)>"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": context}]},
        {"type": "divider"},
    ]
    if file_id:
        blocks += [
            {"type": "image", "slack_file": {"id": file_id}, "alt_text": f"{deck['title']} {n}장 미리보기", "title": {"type": "plain_text", "text": f"전체 {n}장 미리보기"}},
            {"type": "divider"},
        ]
    for p in LABELS:
        if p in deck["captions"]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": CAPTION_TITLES[p] + "\n" + quote(deck["captions"][p])}})
    blocks.append({"type": "divider"})
    if status is not None:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": status}})
        return blocks
    where = platforms_label(deck)
    blocks += [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"<@{owner}> 위 {n}장과 캡션을 확인하고 발행 여부를 선택해 주세요. [발행]을 누르면 {where}에 바로 게시돼요."}},
        {"type": "actions", "block_id": f"confirm_{deck['slug']}", "elements": [
            {"type": "button", "action_id": "publish", "text": {"type": "plain_text", "text": "발행"}, "style": "primary", "value": action_value(deck),
             "confirm": {
                 "title": {"type": "plain_text", "text": "정말 발행할까요?"},
                 "text": {"type": "mrkdwn", "text": f"{where}에 {n}장 캐러셀로 바로 공개 게시돼요. 되돌리려면 게시물을 직접 지워야 해요."},
                 "confirm": {"type": "plain_text", "text": "발행"},
                 "deny": {"type": "plain_text", "text": "돌아가기"},
                 "style": "primary",
             }},
            {"type": "button", "action_id": "cancel", "text": {"type": "plain_text", "text": "발행 취소"}, "style": "danger", "value": action_value(deck)},
        ]},
    ]
    return blocks


def status_publishing(deck, user, when):
    return f":hourglass_flowing_sand: <@{user}> 님이 발행을 승인했어요 · {when}\n{platforms_label(deck)}에 게시하는 중이에요…"


def status_cancelled(user, when):
    return f":no_entry_sign: <@{user}> 님이 발행을 취소했어요 · {when}"


def status_result(user, when, result):
    lines = [f":white_check_mark: <@{user}> 님이 발행을 승인했어요 · {when}"]
    if result.get("fatal"):
        lines.append(f":warning: 게시하지 못했어요 — {result['fatal'][:600]}")
        return "\n".join(lines)
    if result.get("dry_run"):
        lines.append(f":information_source: 실제 게시는 건너뛰었어요 — {result['reason'][:600]}")
        return "\n".join(lines)
    for name, label in LABELS.items():
        r = result.get("results", {}).get(name)
        if r is None:
            if name in result.get("skipped", {}):
                lines.append(f"• {label}: 건너뜀 — {result['skipped'][name]}")
        elif r.get("error"):
            lines.append(f"• {label}: :warning: 실패 — {r['error'][:400]}")
        elif r.get("permalink"):
            lines.append(f"• {label}: <{r['permalink']}|게시물 보기>")
        else:
            lines.append(f"• {label}: 게시 완료 (id {r.get('id')})")
    return "\n".join(lines)
