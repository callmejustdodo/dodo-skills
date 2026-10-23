"""발행 흐름 테스트. 실제 API 대신 로컬 가짜 서버(Supabase Storage·인스타·스레드)를 띄워 끝까지 돌린다.

    uv run --with requests --with pillow --with pytest python -m pytest -q scripts/test_publish.py
"""
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck as decklib  # noqa: E402
import messages  # noqa: E402
import prepare_deck  # noqa: E402
import publisher  # noqa: E402

SB_KEY, IG_TOK, TH_TOK = "sb_secret_TESTKEY_123456", "IGTESTTOKEN_abcdefgh", "THTESTTOKEN_abcdefgh"
CAPTIONS = {"instagram": "인스타 캡션 테스트\n\n#테스트", "threads": "스레드 본문 테스트"}


@pytest.fixture
def deck(tmp_path, monkeypatch):
    monkeypatch.setattr(decklib, "STATE_DIR", str(tmp_path / "state"))
    d = tmp_path / "decks" / "test-deck"
    (d / "png").mkdir(parents=True)
    for i in range(1, 5):
        Image.new("RGB", (1080, 1350), (40 * i, 120, 200)).save(d / "png" / f"slide-{i:02d}.png")
    (d / "deck.json").write_text(json.dumps({"slug": "test-deck", "title": "테스트 덱", "summary": "요약", "figma_url": "https://figma.com/x",
                                             "meta": "1080×1350", "warning": "테스트 경고", "trigger": "TRIGGER123",
                                             "preview": {"eyebrow": "카드뉴스", "title": ["테스트"], "lines": ["4장"], "colors": ["#A66BEE"]}}))
    (d / "captions.json").write_text(json.dumps(CAPTIONS, ensure_ascii=False))
    meta = json.loads((d / "deck.json").read_text())
    prepare_deck.build_preview(prepare_deck.to_jpeg(str(d)), meta["preview"], str(d / "preview.png"))
    return decklib.load_deck(str(d))


class Fake:
    def __init__(self, fail_threads_carousel=False, flaky_items=None, permanent_item_error=None, flaky_publish=None):
        self.fail_threads_carousel = fail_threads_carousel
        self.flaky_items = dict(flaky_items or {})  # {("ig", 3): 2} → 3번째 인스타 이미지가 일시 오류 2번 뒤 성공
        self.permanent_item_error = permanent_item_error  # ("ig", 2) → 그 이미지는 영구 오류
        self.flaky_publish = flaky_publish  # "th" → 게시 단계에서 일시 오류
        self.item_attempts = {}
        self.bucket, self.objects, self.containers, self.calls, self.n = None, {}, {}, [], 0

    def new_id(self, prefix):
        self.n += 1
        return f"{prefix}{self.n}"


def make_server(fake):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def graph_error(self, msg, transient=False):
            self.send(400, {"error": {"message": msg, "type": "OAuthException", "code": 2 if transient else 100, "is_transient": transient}})

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            fake.calls.append(("GET", u.path))
            if u.path == "/storage/v1/bucket/card-news":
                if self.headers.get("apikey") != SB_KEY:
                    return self.send(401, {"error": "Unauthorized", "message": "Invalid API key"})
                return self.send(200, {"id": "card-news", "public": True}) if fake.bucket else self.send(400, {"error": "Bucket not found", "message": "Bucket not found"})
            if u.path.startswith("/storage/v1/object/public/card-news/"):
                key = u.path[len("/storage/v1/object/public/card-news/"):]
                return self.send(200, fake.objects[key], "image/jpeg") if key in fake.objects else self.send(400, {"error": "not_found"})
            for prefix, tok, field in (("/ig/", IG_TOK, "status_code"), ("/th/", TH_TOK, "status")):
                if u.path.startswith(prefix):
                    if q.get("access_token") != tok:
                        return self.graph_error("Invalid OAuth access token")
                    cid = u.path[len(prefix):]
                    if q.get("fields") == "permalink":
                        return self.send(200, {"id": cid, "permalink": f"https://example.com/{prefix.strip('/')}/{cid}"})
                    c = fake.containers.get(cid)
                    if not c:
                        return self.graph_error("Unknown container")
                    status = c["statuses"].pop(0) if len(c["statuses"]) > 1 else c["statuses"][0]
                    return self.send(200, {"id": cid, field: status})
            self.send(404, {"error": "no route"})

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            fake.calls.append(("POST", u.path))
            if u.path == "/storage/v1/bucket":
                if self.headers.get("apikey") != SB_KEY:
                    return self.send(401, {"error": "Unauthorized"})
                fake.bucket = json.loads(raw)
                return self.send(200, {"name": fake.bucket["name"]})
            if u.path.startswith("/storage/v1/object/card-news/"):
                if self.headers.get("apikey") != SB_KEY or self.headers.get("Authorization"):
                    return self.send(401, {"error": "Unauthorized"})
                if self.headers.get("Content-Type") != "image/jpeg" or raw[:3] != b"\xff\xd8\xff":
                    return self.send(400, {"error": "invalid_mime_type"})
                key = u.path[len("/storage/v1/object/card-news/"):]
                fake.objects[key] = raw
                return self.send(200, {"Key": f"card-news/{key}"})
            form = dict(urllib.parse.parse_qsl(raw.decode()))
            for prefix, tok, create, publish in (("/ig/", IG_TOK, "media", "media_publish"), ("/th/", TH_TOK, "threads", "threads_publish")):
                if not u.path.startswith(prefix):
                    continue
                if form.get("access_token") != tok:
                    return self.graph_error("Invalid OAuth access token")
                edge = u.path[len(prefix):].partition("/")[2]
                if edge == create and form.get("media_type") == "CAROUSEL":
                    if prefix == "/th/" and fake.fail_threads_carousel:
                        return self.graph_error("(#100) mock carousel failure")
                    kids = form["children"].split(",")
                    if not 2 <= len(kids) <= 20 or any(k not in fake.containers for k in kids):
                        return self.graph_error("bad children")
                    cid = fake.new_id(prefix.strip("/") + "car")
                    fake.containers[cid] = {"kind": "carousel", "children": kids, "caption": form.get("caption") or form.get("text"), "statuses": ["IN_PROGRESS", "FINISHED"]}
                    return self.send(200, {"id": cid})
                if edge == create:
                    if form.get("is_carousel_item") != "true":
                        return self.graph_error("expected carousel item")
                    plat = prefix.strip("/")
                    idx = int(form["image_url"].rsplit("slide-", 1)[1][:2])
                    fake.item_attempts[(plat, idx)] = fake.item_attempts.get((plat, idx), 0) + 1
                    if fake.permanent_item_error == (plat, idx):
                        return self.graph_error("(#100) Invalid parameter")
                    if fake.flaky_items.get((plat, idx), 0) > 0:
                        fake.flaky_items[(plat, idx)] -= 1
                        return self.graph_error("Timeout", transient=True)
                    with urllib.request.urlopen(form["image_url"]) as r:  # 공개 URL에서 실제로 받아 본다
                        if r.headers.get("Content-Type") != "image/jpeg" or r.read(3) != b"\xff\xd8\xff":
                            return self.graph_error("image is not a public JPEG")
                    cid = fake.new_id(prefix.strip("/") + "img")
                    fake.containers[cid] = {"kind": "image", "url": form["image_url"], "statuses": ["FINISHED"]}
                    return self.send(200, {"id": cid})
                if edge == publish:
                    fake.calls.append(("PUBLISH", prefix.strip("/")))
                    if fake.flaky_publish == prefix.strip("/"):
                        return self.graph_error("An unknown error occurred", transient=True)
                    c = fake.containers.get(form.get("creation_id"))
                    if not c or c["kind"] != "carousel" or c["statuses"][0] != "FINISHED":
                        return self.graph_error("container not ready")
                    return self.send(200, {"id": fake.new_id(prefix.strip("/") + "post")})
            self.send(404, {"error": "no route"})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def server():
    servers = []

    def start(**kw):
        fake = Fake(**kw)
        srv = make_server(fake)
        servers.append(srv)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        env = {"SUPABASE_URL": base, "SUPABASE_SECRET_KEY": SB_KEY, "SUPABASE_BUCKET": "card-news",
               "IG_USER_ID": "17841400000000000", "IG_ACCESS_TOKEN": IG_TOK, "IG_GRAPH_BASE": f"{base}/ig",
               "THREADS_USER_ID": "26000000000000000", "THREADS_ACCESS_TOKEN": TH_TOK, "THREADS_GRAPH_BASE": f"{base}/th",
               "PUBLISH_POLL_INTERVAL": "0.05", "PUBLISH_POLL_TIMEOUT": "5", "PUBLISH_RETRY_BASE": "0.01", "PUBLISH_ITEM_GAP": "0"}
        return fake, env

    yield start
    for s in servers:
        s.shutdown()


quiet = lambda *a: None  # noqa: E731


def test_prepare_deck_outputs(deck):
    assert len(deck["slides"]) == 4 and publisher.validate_assets(deck) == []
    assert Image.open(deck["preview"]).size == (2*72 + 3*540 + 2*36, 2*72 + 2*675 + 36)  # 4장 + 요약 타일 → 3열 2행


def test_full_publish(deck, server):
    fake, env = server()
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert out["dry_run"] is False
    assert fake.bucket == {"id": "card-news", "name": "card-news", "public": True}
    assert len(fake.objects) == 4 and all(k.startswith("test-deck/") for k in fake.objects)
    assert out["results"]["instagram"]["permalink"].startswith("https://example.com/ig/igpost")
    assert out["results"]["threads"]["permalink"].startswith("https://example.com/th/thpost")
    carousels = [c for c in fake.containers.values() if c["kind"] == "carousel"]
    assert sorted(c["caption"] for c in carousels) == sorted(CAPTIONS.values())
    ig_car = next(c for c in carousels if c["caption"] == CAPTIONS["instagram"])
    assert [fake.containers[k]["url"].rsplit("/", 1)[1] for k in ig_car["children"]] == [f"slide-{i:02d}.jpg" for i in range(1, 5)]
    assert os.path.exists(decklib.state_path("publish_log.jsonl"))


def test_partial_failure_keeps_instagram_and_redacts_tokens(deck, server):
    fake, env = server(fail_threads_carousel=True)
    out = publisher.publish_all(deck, env=env, log=quiet)
    err = out["results"]["threads"]["error"]
    assert out["results"]["instagram"]["permalink"] and "mock carousel failure" in err and TH_TOK not in err
    status = messages.status_result("U1", "10/24 00:00", out)
    assert "인스타그램: <https://example.com/ig/" in status and "스레드: :warning: 실패" in status


def test_dry_run_without_account_keys_makes_no_calls(deck, server):
    fake, env = server()
    env.update(IG_USER_ID="", IG_ACCESS_TOKEN="", THREADS_USER_ID="", THREADS_ACCESS_TOKEN="")
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert out["dry_run"] and "IG_USER_ID" in out["reason"] and fake.calls == []
    assert "실제 게시는 건너뛰었어요" in messages.status_result("U1", "10/24 00:00", out)


def test_dry_run_flag_and_missing_storage(deck, server):
    fake, env = server()
    assert "PUBLISH_DRY_RUN" in publisher.publish_all(deck, env={**env, "PUBLISH_DRY_RUN": "1"}, log=quiet)["reason"]
    assert "SUPABASE_SECRET_KEY" in publisher.publish_all(deck, env={**env, "SUPABASE_SECRET_KEY": ""}, log=quiet)["reason"]
    assert fake.calls == []


def test_only_instagram_keys(deck, server):
    fake, env = server()
    env.update(THREADS_USER_ID="", THREADS_ACCESS_TOKEN="")
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert list(out["results"]) == ["instagram"] and "THREADS_USER_ID" in out["skipped"]["threads"]
    assert "스레드: 건너뜀" in messages.status_result("U1", "10/24 00:00", out)


def test_bad_storage_key_is_fatal_and_redacted(deck, server):
    fake, env = server()
    env["SUPABASE_SECRET_KEY"] = "sb_secret_WRONGKEY_999"
    with pytest.raises(publisher.PublishError) as e:
        publisher.publish_all(deck, env=env, log=quiet)
    assert "이미지 업로드 실패" in str(e.value) and "WRONGKEY" not in str(e.value)


def test_transient_item_errors_are_retried(deck, server):
    fake, env = server(flaky_items={("ig", 3): 2, ("th", 4): 3})
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert out["results"]["instagram"]["permalink"] and out["results"]["threads"]["permalink"]
    assert fake.item_attempts[("ig", 3)] == 3 and fake.item_attempts[("th", 4)] == 4


def test_retries_give_up_after_four_attempts(deck, server):
    fake, env = server(flaky_items={("ig", 2): 9})
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert "Timeout" in out["results"]["instagram"]["error"] and fake.item_attempts[("ig", 2)] == 4
    assert out["results"]["threads"]["permalink"]


def test_permanent_errors_are_not_retried(deck, server):
    fake, env = server(permanent_item_error=("ig", 2))
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert "Invalid parameter" in out["results"]["instagram"]["error"] and fake.item_attempts[("ig", 2)] == 1


def test_publish_step_is_never_retried(deck, server):
    fake, env = server(flaky_publish="th")
    out = publisher.publish_all(deck, env=env, log=quiet)
    assert "unknown error" in out["results"]["threads"]["error"]
    assert fake.calls.count(("PUBLISH", "th")) == 1 and out["results"]["instagram"]["permalink"]


def test_only_limits_platforms(deck, server):
    fake, env = server()
    out = publisher.publish_all(deck, env=env, log=quiet, only=["threads"])
    assert list(out["results"]) == ["threads"] and out["skipped"] == {}
    assert ("PUBLISH", "ig") not in fake.calls


def test_retry_button_carries_failed_platforms(deck):
    result = {"results": {"instagram": {"error": "Timeout"}, "threads": {"id": "1", "permalink": "https://t/1"}}, "skipped": {}}
    retry = messages.failed_platforms(result, ["instagram", "threads"])
    assert retry == ["instagram"] and messages.failed_platforms({"fatal": "x"}, ["instagram", "threads"]) == ["instagram", "threads"]
    blocks = messages.build_blocks(deck, "U1", "F1", status=messages.status_result("U1", "now", result), retry=retry)
    btn = blocks[-1]["elements"][0]
    assert btn["action_id"] == "retry" and btn["value"] == "test-deck:v2:instagram" and len(btn["confirm"]["text"]["text"]) <= 300
    assert messages.build_blocks(deck, "U1", "F1", status="done", retry=[])[-1]["type"] == "section"


def test_redact():
    env = {"IG_ACCESS_TOKEN": IG_TOK, "THREADS_ACCESS_TOKEN": TH_TOK, "SUPABASE_SECRET_KEY": SB_KEY}
    assert publisher.redact(f"?access_token={IG_TOK}&b={TH_TOK} k={SB_KEY}", env) == "?access_token=***&b=*** k=***"


@pytest.mark.parametrize("status", [None, "publishing", "cancelled", "result"])
def test_blocks_fit_slack_limits(deck, status):
    text = {None: None, "publishing": messages.status_publishing(deck, "U1", "10/24 00:00"),
            "cancelled": messages.status_cancelled("U1", "10/24 00:00"),
            "result": messages.status_result("U1", "10/24 00:00", {"results": {"instagram": {"id": "1", "permalink": "https://i/p/1"}, "threads": {"error": "x" * 900}}, "skipped": {}})}[status]
    blocks = messages.build_blocks(deck, "U0AN3UQG23Y", "F123", status=text)
    assert len(blocks) <= 50
    for b in blocks:
        texts = [b["text"]["text"]] if b["type"] in ("section", "header") else [e["text"] for e in b.get("elements", []) if b["type"] == "context"]
        assert all(len(t) <= (150 if b["type"] == "header" else 3000) for t in texts)
    actions = [b for b in blocks if b["type"] == "actions"]
    if status is None:
        publish, cancel = actions[0]["elements"]
        c = publish["confirm"]
        assert len(c["title"]["text"]) <= 100 and len(c["text"]["text"]) <= 300 and len(c["confirm"]["text"]) <= 30 and len(c["deny"]["text"]) <= 30
        assert publish["value"] == cancel["value"] == "test-deck:v2" and "confirm" not in cancel
    else:
        assert actions == []


def test_registered_decks_are_valid():
    decks = decklib.all_decks()
    if not decks:
        pytest.skip("등록된 덱 없음")
    for d in decks:
        assert publisher.validate_assets(d) == [], d["slug"]
