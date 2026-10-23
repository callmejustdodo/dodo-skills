"""카드뉴스 컨펌 봇 (룰 기반, AI 호출 없음).

허용된 사용자의 메시지에 덱의 trigger 문자열이 있으면 trigger_delay_sec 뒤
미리보기 + 피그마 링크 + 캡션 + [발행]/[발행 취소] 버튼으로 컨펌을 요청한다.
[발행](확인창 통과)을 누르면 publisher로 인스타그램·스레드에 게시하고 결과로 메시지를 갱신한다.
덱은 메시지마다 decks/에서 다시 읽으므로 새 덱을 추가해도 재시작이 필요 없다.
"""
import json
import os
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slack_bolt import App  # noqa: E402
from slack_bolt.adapter.socket_mode import SocketModeHandler  # noqa: E402

import deck as decklib  # noqa: E402
import messages  # noqa: E402
import publisher  # noqa: E402
import slack_io  # noqa: E402

ENV = decklib.load_env()
HOME_CHANNEL = ENV["SLACK_CHANNEL"]
ALLOWED = set(ENV["SLACK_ALLOWED_USERS"].split(","))
OWNER = ENV["SLACK_ALLOWED_USERS"].split(",")[0]
DEFAULT_DELAY = 30

app = App(token=ENV["SLACK_BOT_TOKEN"])
client = app.client
START_TS = time.time()
seen, busy = set(), set()
lock = threading.Lock()


def log(*args):
    print(datetime.now().strftime("%H:%M:%S"), *args, flush=True)


def deliver(deck, channel, thread_ts):
    try:
        file_id = slack_io.preview_file_id(client, deck, log)  # 대기 전에 올려 두면 Slack이 그 사이 처리한다
    except Exception as e:
        log("preview upload failed:", repr(e))
        file_id = None
    delay = int(deck.get("trigger_delay_sec", DEFAULT_DELAY))
    log(f"waiting {delay}s before posting {deck['slug']} to {channel}")
    time.sleep(delay)
    slack_io.post_confirm(client, deck, channel, OWNER, file_id, thread_ts, log)


def consider(channel, user, text, ts, thread_ts):
    if user not in ALLOWED or not text or float(ts) < START_TS:
        return
    for deck in decklib.all_decks():
        if not deck.get("trigger") or deck["trigger"] not in text:
            continue
        with lock:
            if (ts, deck["slug"]) in seen:
                continue
            seen.add((ts, deck["slug"]))
        log(f"trigger {deck['slug']} from {user} in {channel} (ts={ts})")
        threading.Thread(target=deliver, args=(deck, channel, thread_ts), daemon=True).start()


@app.event("message")
def on_message(event):
    if event.get("subtype") not in (None, "thread_broadcast", "file_share"):
        return
    consider(event.get("channel"), event.get("user"), event.get("text"), event.get("ts"), event.get("thread_ts"))


@app.event("app_mention")
def on_mention(event):
    consider(event.get("channel"), event.get("user"), event.get("text"), event.get("ts"), event.get("thread_ts"))


def poll_home():
    """이벤트 구독이 없을 때를 대비해 홈 채널을 주기적으로 확인한다."""
    while True:
        try:
            res = client.conversations_history(channel=HOME_CHANNEL, oldest=f"{START_TS:.6f}", limit=20)
            for m in res.get("messages", []):
                if m.get("subtype") in (None, "thread_broadcast", "file_share"):
                    consider(HOME_CHANNEL, m.get("user"), m.get("text"), m.get("ts"), m.get("thread_ts"))
            time.sleep(4)
        except Exception as e:
            log("poll error:", repr(e))
            time.sleep(15)


def record(entry):
    with open(decklib.state_path("decisions.jsonl"), "a") as f:
        f.write(json.dumps({"at": datetime.now().isoformat(), **entry}, ensure_ascii=False) + "\n")


def update(deck, channel, ts, file_id, status, prefix, retry=None):
    client.chat_update(channel=channel, ts=ts, text=messages.fallback_text(deck, prefix),
                       blocks=messages.build_blocks(deck, OWNER, file_id, status=status, retry=retry))


def message_results(ts, result=None):
    """메시지별 최신 게시 결과. 재시도 때 성공했던 플랫폼 링크를 유지하는 데 쓴다."""
    path = decklib.state_path("message_results.json")
    data = json.load(open(path)) if os.path.exists(path) else {}
    if result is None:
        return data.get(ts, {})
    data[ts] = {"results": result.get("results", {}), "skipped": result.get("skipped", {})}
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)


def run_publish(deck, channel, ts, user, when, file_id, only=None):
    attempted = only or [p for p in messages.LABELS if p in deck["captions"]]
    try:
        result = publisher.publish_all(deck, log=log, only=only)
    except Exception as e:
        result = {"fatal": publisher.redact(str(e))}
    if only and not result.get("fatal") and not result.get("dry_run"):
        prev = message_results(ts)
        result = {**result, "results": {**prev.get("results", {}), **result["results"]},
                  "skipped": {**prev.get("skipped", {}), **result.get("skipped", {})}}
    if not result.get("fatal") and not result.get("dry_run"):
        message_results(ts, result)
    log("publish result:", json.dumps(result, ensure_ascii=False)[:600])
    update(deck, channel, ts, file_id, messages.status_result(user, when, result, retried=bool(only)), "카드뉴스 발행 결과",
           retry=messages.failed_platforms(result, attempted))
    record({"slug": deck["slug"], "decision": "retry" if only else "publish", "only": only, "user": user, "message_ts": ts, "result": result})
    with lock:
        busy.discard(ts)


def decide(ack, body, kind):
    ack()
    slug, _, rest = (body["actions"][0].get("value") or "").partition(":")
    version, _, platforms = rest.partition(":")
    only = [p for p in platforms.split(",") if p in messages.LABELS] if kind == "retry" else None
    channel, user, ts = body["channel"]["id"], body["user"]["id"], body["message"]["ts"]
    if kind == "retry" and not only:
        return
    if not version:
        client.chat_postEphemeral(channel=channel, user=user, text="이전 버전 컨펌 메시지예요. 원본 링크를 다시 보내 주시면 캡션과 확인창이 있는 새 요청을 드릴게요.")
        return
    if user not in ALLOWED:
        client.chat_postEphemeral(channel=channel, user=user, text="발행 여부는 담당자만 선택할 수 있어요.")
        return
    try:
        deck = decklib.load_deck(slug)
    except FileNotFoundError:
        client.chat_postEphemeral(channel=channel, user=user, text=f"'{slug}' 덱을 찾을 수 없어요. 스킬의 decks/ 폴더를 확인해 주세요.")
        return
    with lock:
        if ts in busy:
            return
        busy.add(ts)
    when = datetime.now().strftime("%m/%d %H:%M")
    file_id = next((b["slack_file"]["id"] for b in body["message"].get("blocks", []) if b.get("type") == "image" and b.get("slack_file")), None)
    log(f"decision: {kind} {slug} by {user} (message {ts})")
    if kind == "cancel":
        update(deck, channel, ts, file_id, messages.status_cancelled(user, when), "카드뉴스 발행 취소")
        record({"slug": slug, "decision": "cancel", "user": user, "message_ts": ts})
        return
    update(deck, channel, ts, file_id, messages.status_publishing(deck, user, when, only), "카드뉴스 발행 중")
    threading.Thread(target=run_publish, args=(deck, channel, ts, user, when, file_id, only), daemon=True).start()


@app.action("publish")
def on_publish(ack, body):
    decide(ack, body, "publish")


@app.action("retry")
def on_retry(ack, body):
    decide(ack, body, "retry")


@app.action("cancel")
def on_cancel(ack, body):
    decide(ack, body, "cancel")


if __name__ == "__main__":
    if slack_io.bot_running():
        sys.exit("already running (state/bot.pid)")
    with open(decklib.state_path("bot.pid"), "w") as f:
        f.write(str(os.getpid()))
    threading.Thread(target=poll_home, daemon=True).start()
    triggers = {d["slug"]: d.get("trigger") for d in decklib.all_decks()}
    log(f"ready · decks {triggers} · allowed {sorted(ALLOWED)}")
    SocketModeHandler(app, ENV["SLACK_APP_TOKEN"]).start()
