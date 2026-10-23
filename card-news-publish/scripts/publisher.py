"""덱 발행: JPEG → Supabase 공개 버킷 → 인스타그램·스레드 캐러셀.

키는 발행할 때마다 .env에서 다시 읽는다. 키가 없거나 PUBLISH_DRY_RUN=1이면
네트워크 호출 없이 무엇을 건너뛰었는지만 돌려준다. 게시는 Slack [발행] 승인으로만 일어난다.

    python publisher.py check [slug]     # 키·이미지·캡션 점검 (키 값은 출력하지 않음)
    python publisher.py refresh-tokens   # 인스타·스레드 장기 토큰 60일 연장
"""
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck as decklib  # noqa: E402

IG_KEYS = ("IG_USER_ID", "IG_ACCESS_TOKEN")
TH_KEYS = ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN")
SB_KEYS = ("SUPABASE_URL", "SUPABASE_SECRET_KEY")
SECRET_KEYS = ("IG_ACCESS_TOKEN", "THREADS_ACCESS_TOKEN", "SUPABASE_SECRET_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN")
PLATFORMS = (("instagram", "인스타그램", IG_KEYS), ("threads", "스레드", TH_KEYS))
IG_BASE = "https://graph.instagram.com/v23.0"
TH_BASE = "https://graph.threads.net/v1.0"


class PublishError(Exception):
    pass


def missing(env, keys):
    return [k for k in keys if not env.get(k, "").strip()]


def redact(text, env=None):
    env = env if env is not None else decklib.load_env()
    for k in SECRET_KEYS:
        v = env.get(k, "")
        if len(v) >= 8:
            text = text.replace(v, "***")
    return text


def validate_assets(deck):
    errs, files, captions = [], deck["slides"], deck["captions"]
    if not 2 <= len(files) <= 20:
        errs.append(f"슬라이드가 {len(files)}장이에요 (캐러셀은 2~20장)")
    for p in files:
        with open(p, "rb") as f:
            if f.read(3) != b"\xff\xd8\xff":
                errs.append(f"{os.path.basename(p)}가 JPEG가 아니에요")
        if os.path.getsize(p) > 8 * 1024 * 1024:
            errs.append(f"{os.path.basename(p)}가 8MB를 넘어요")
    ig, th = captions.get("instagram"), captions.get("threads")
    if ig is not None and not 1 <= len(ig) <= 2200:
        errs.append(f"인스타 캡션 길이 {len(ig)}자 (1~2,200자)")
    if ig is not None and ig.count("#") > 30:
        errs.append(f"인스타 해시태그 {ig.count('#')}개 (최대 30개)")
    if th is not None and not 1 <= len(th) <= 500:
        errs.append(f"스레드 본문 길이 {len(th)}자 (1~500자)")
    if ig is None and th is None:
        errs.append("captions.json에 instagram·threads 캡션이 없어요")
    return errs


def _check(resp, what):
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text[:300]}
    err = data.get("error") if isinstance(data, dict) else None
    if resp.status_code >= 400 or err:
        msg = err.get("message") if isinstance(err, dict) else (data.get("message") or err or data.get("raw") or "")
        raise PublishError(f"{what} 실패 ({resp.status_code}): {msg}")
    return data


# ── Supabase Storage ─────────────────────────────────────────────

def _sb(env):
    return env["SUPABASE_URL"].rstrip("/"), env["SUPABASE_SECRET_KEY"], (env.get("SUPABASE_BUCKET") or "card-news")


def _sb_headers(key, extra=None):
    headers = {"apikey": key}
    if key.startswith("eyJ"):  # legacy service_role JWT
        headers["Authorization"] = f"Bearer {key}"
    headers.update(extra or {})
    return headers


def ensure_bucket(env):
    url, key, bucket = _sb(env)
    r = requests.get(f"{url}/storage/v1/bucket/{bucket}", headers=_sb_headers(key), timeout=20)
    if r.status_code == 200:
        if not r.json().get("public"):
            raise PublishError(f"Supabase 버킷 '{bucket}'이 비공개예요. 공개 버킷으로 바꾸거나 SUPABASE_BUCKET을 비워 주세요")
        return bucket
    r = requests.post(f"{url}/storage/v1/bucket", headers=_sb_headers(key, {"Content-Type": "application/json"}),
                      json={"id": bucket, "name": bucket, "public": True}, timeout=20)
    _check(r, f"Supabase 버킷 '{bucket}' 생성")
    return bucket


def upload_slides(env, files, prefix):
    url, key, bucket = _sb(env)
    urls = []
    for p in files:
        path = f"{prefix}/{os.path.basename(p)}"
        with open(p, "rb") as f:
            r = requests.post(f"{url}/storage/v1/object/{bucket}/{path}", data=f.read(), timeout=60,
                              headers=_sb_headers(key, {"Content-Type": "image/jpeg", "x-upsert": "true", "cache-control": "3600"}))
        _check(r, f"Supabase 업로드 {os.path.basename(p)}")
        public = f"{url}/storage/v1/object/public/{bucket}/{path}"
        chk = requests.get(public, timeout=20)
        if chk.status_code != 200 or not chk.headers.get("content-type", "").startswith("image/jpeg"):
            raise PublishError(f"공개 URL을 열 수 없어요 ({chk.status_code}): {public}")
        urls.append(public)
    return urls


# ── Instagram / Threads (Meta Graph) ─────────────────────────────

def _post(url, what, **params):
    return _check(requests.post(url, data=params, timeout=60), what)


def _get(url, what, **params):
    return _check(requests.get(url, params=params, timeout=30), what)


def _wait(fetch, field, label, interval, timeout):
    deadline = time.time() + timeout
    while True:
        data = fetch()
        status = data.get(field)
        if status in ("FINISHED", "PUBLISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            raise PublishError(f"{label} 처리 실패: {status} {data.get('error_message', '')}".strip())
        if time.time() > deadline:
            raise PublishError(f"{label} 처리 대기 시간 초과 (마지막 상태 {status})")
        time.sleep(interval)


def publish_instagram(env, urls, caption, interval, timeout):
    base = env.get("IG_GRAPH_BASE") or IG_BASE
    uid, tok = env["IG_USER_ID"], env["IG_ACCESS_TOKEN"]
    status = lambda cid: _get(f"{base}/{cid}", "인스타 상태 확인", fields="status_code", access_token=tok)
    kids = [_post(f"{base}/{uid}/media", f"인스타 이미지 컨테이너 {i + 1}", image_url=u, is_carousel_item="true", access_token=tok)["id"]
            for i, u in enumerate(urls)]
    for i, cid in enumerate(kids):
        _wait(lambda cid=cid: status(cid), "status_code", f"인스타 이미지 {i + 1}", interval, timeout)
    car = _post(f"{base}/{uid}/media", "인스타 캐러셀 컨테이너", media_type="CAROUSEL", children=",".join(kids), caption=caption, access_token=tok)["id"]
    _wait(lambda: status(car), "status_code", "인스타 캐러셀", interval, timeout)
    media = _post(f"{base}/{uid}/media_publish", "인스타 게시", creation_id=car, access_token=tok)["id"]
    try:
        link = _get(f"{base}/{media}", "인스타 링크 조회", fields="permalink", access_token=tok).get("permalink")
    except PublishError:
        link = None
    return {"id": media, "permalink": link}


def publish_threads(env, urls, text, interval, timeout):
    base = env.get("THREADS_GRAPH_BASE") or TH_BASE
    uid, tok = env["THREADS_USER_ID"], env["THREADS_ACCESS_TOKEN"]
    status = lambda cid: _get(f"{base}/{cid}", "스레드 상태 확인", fields="status,error_message", access_token=tok)
    kids = [_post(f"{base}/{uid}/threads", f"스레드 이미지 컨테이너 {i + 1}", media_type="IMAGE", image_url=u, is_carousel_item="true", access_token=tok)["id"]
            for i, u in enumerate(urls)]
    for i, cid in enumerate(kids):
        _wait(lambda cid=cid: status(cid), "status", f"스레드 이미지 {i + 1}", interval, timeout)
    car = _post(f"{base}/{uid}/threads", "스레드 캐러셀 컨테이너", media_type="CAROUSEL", children=",".join(kids), text=text, access_token=tok)["id"]
    _wait(lambda: status(car), "status", "스레드 캐러셀", interval, timeout)
    post = _post(f"{base}/{uid}/threads_publish", "스레드 게시", creation_id=car, access_token=tok)["id"]
    try:
        link = _get(f"{base}/{post}", "스레드 링크 조회", fields="permalink", access_token=tok).get("permalink")
    except PublishError:
        link = None
    return {"id": post, "permalink": link}


PUBLISHERS = {"instagram": publish_instagram, "threads": publish_threads}


def publish_all(deck, env=None, log=print):
    """발행 결과를 돌려준다. 업로드 전 단계 실패는 PublishError로 올린다."""
    env = env if env is not None else decklib.load_env()
    errs = validate_assets(deck)
    if errs:
        raise PublishError(" / ".join(errs))

    targets, skipped = [], {}
    for name, label, keys in PLATFORMS:
        gaps = missing(env, keys)
        if name not in deck["captions"]:
            skipped[name] = "captions.json에 캡션 없음"
        elif gaps:
            skipped[name] = "키 없음 (" + ", ".join(gaps) + ")"
        else:
            targets.append(name)
    out = {"dry_run": True, "reason": "", "targets": targets, "skipped": skipped, "results": {}, "urls": []}
    if env.get("PUBLISH_DRY_RUN", "").lower() in ("1", "true", "yes"):
        out["reason"] = "드라이런 모드(PUBLISH_DRY_RUN=1)라 게시하지 않았어요"
    elif not targets:
        out["reason"] = "게시할 수 있는 계정이 없어요 (" + "; ".join(f"{n}: {r}" for n, r in skipped.items()) + ")"
    elif missing(env, SB_KEYS):
        out["reason"] = "이미지 저장소 키가 없어요 (" + ", ".join(missing(env, SB_KEYS)) + ")"
    if out["reason"]:
        log("publish skipped:", out["reason"])
        return out

    out["dry_run"] = False
    interval = float(env.get("PUBLISH_POLL_INTERVAL") or 5)
    timeout = float(env.get("PUBLISH_POLL_TIMEOUT") or 180)
    prefix = f"{deck['slug']}/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    try:
        ensure_bucket(env)
        out["urls"] = upload_slides(env, deck["slides"], prefix)
    except (PublishError, requests.RequestException) as e:
        raise PublishError(redact(f"이미지 업로드 실패: {e}", env)) from None
    log(f"uploaded {len(out['urls'])} slides → {prefix}")
    for name in targets:
        try:
            out["results"][name] = PUBLISHERS[name](env, out["urls"], deck["captions"][name], interval, timeout)
            log(f"{name} published:", out["results"][name])
        except (PublishError, requests.RequestException) as e:
            out["results"][name] = {"error": redact(str(e), env)}
            log(f"{name} failed:", out["results"][name]["error"])
    with open(decklib.state_path("publish_log.jsonl"), "a") as f:
        f.write(json.dumps({"slug": deck["slug"], "at": datetime.now().isoformat(), "prefix": prefix,
                            "results": out["results"], "skipped": skipped}, ensure_ascii=False) + "\n")
    return out


# ── 토큰 갱신 / 점검 ─────────────────────────────────────────────

def _write_env(updates, path=None):
    path = path or decklib.ENV_PATH
    lines = open(path).read().split("\n")
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in updates and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={updates[key]}"
    with open(path, "w") as f:
        f.write("\n".join(lines))


def refresh_tokens():
    env, updates = decklib.load_env(), {}
    for key, url, grant in (("IG_ACCESS_TOKEN", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
                            ("THREADS_ACCESS_TOKEN", "https://graph.threads.net/refresh_access_token", "th_refresh_token")):
        if not env.get(key):
            print(f"{key}: 비어 있어서 건너뜀")
            continue
        try:
            data = _get(url, f"{key} 갱신", grant_type=grant, access_token=env[key])
            updates[key] = data["access_token"]
            print(f"{key}: 갱신 완료 (만료까지 {int(data.get('expires_in', 0)) // 86400}일)")
        except (PublishError, requests.RequestException) as e:
            print(f"{key}: 갱신 실패 — {redact(str(e), env)}")
    if updates:
        _write_env(updates)


def check(slug=None):
    env = decklib.load_env()
    for group, keys in (("Slack", ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL", "SLACK_ALLOWED_USERS")),
                        ("인스타그램", IG_KEYS), ("스레드", TH_KEYS), ("Supabase", SB_KEYS)):
        gaps = missing(env, keys)
        print(f"{group}: {'준비됨' if not gaps else '빠진 키 ' + ', '.join(gaps)}")
    print("드라이런:", env.get("PUBLISH_DRY_RUN") or "0")
    decks = [decklib.load_deck(slug)] if slug else decklib.all_decks()
    for d in decks:
        errs = validate_assets(d)
        caps = ", ".join(f"{k} {len(v)}자" for k, v in d["captions"].items())
        print(f"[{d['slug']}] 슬라이드 {len(d['slides'])}장 · {caps} · 트리거 {d.get('trigger') or '없음'} → {'문제 없음' if not errs else ' / '.join(errs)}")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else "check"), sys.argv[2:]
    if cmd == "check":
        check(*args[:1])
    elif cmd == "refresh-tokens":
        refresh_tokens()
    else:
        sys.exit(__doc__)
