"""Slack 쪽 공통 동작: 미리보기 업로드(캐시)와 컨펌 메시지 전송."""
import json
import os

import deck as decklib
import messages


def preview_file_id(client, deck, log=print):
    """덱 미리보기를 채널에 공유하지 않고 업로드해 file id를 돌려준다. preview.png가 그대로면 재사용."""
    cache_path = decklib.state_path("preview_ids.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    mtime = os.path.getmtime(deck["preview"])
    hit = cache.get(deck["slug"])
    if hit and hit.get("mtime") == mtime:
        try:
            if client.files_info(file=hit["file_id"]).get("ok"):
                return hit["file_id"]
        except Exception:
            pass
    res = client.files_upload_v2(file=deck["preview"], filename=f"{deck['slug']}-preview.png",
                                 title=f"{deck['title']} · 전체 {len(deck['slides'])}장 미리보기")
    cache[deck["slug"]] = {"file_id": res["file"]["id"], "mtime": mtime}
    with open(cache_path, "w") as f:
        json.dump(cache, f)
    log("preview uploaded:", deck["slug"], res["file"]["id"])
    return res["file"]["id"]


def post_confirm(client, deck, channel, owner, file_id, thread_ts=None, log=print):
    try:
        res = client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=messages.fallback_text(deck),
                                      blocks=messages.build_blocks(deck, owner, file_id), unfurl_links=False, unfurl_media=False)
    except Exception as e:
        log("post with image block failed:", repr(e), "→ fallback: preview file in thread")
        res = client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=messages.fallback_text(deck),
                                      blocks=messages.build_blocks(deck, owner), unfurl_links=False, unfurl_media=False)
        client.files_upload_v2(channel=channel, thread_ts=res["ts"], file=deck["preview"],
                               filename=f"{deck['slug']}-preview.png", title=f"전체 {len(deck['slides'])}장 미리보기")
    log("posted confirm:", deck["slug"], res["ts"])
    return res["ts"]


def bot_running():
    pidfile = decklib.state_path("bot.pid")
    if not os.path.exists(pidfile):
        return False
    try:
        os.kill(int(open(pidfile).read()), 0)
        return True
    except (OSError, ValueError):
        return False
