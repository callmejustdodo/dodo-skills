"""스킬 경로, .env, 덱(카드뉴스 한 묶음) 로딩.

덱 폴더 구조 (decks/<slug>/):
    deck.json      제목·설명·피그마 링크·트리거 등 메타데이터
    captions.json  {"instagram": "...", "threads": "..."}
    png/           피그마에서 내보낸 원본 PNG (prepare_deck.py 입력)
    slides/        slide-01.jpg … 게시용 JPEG
    preview.png    Slack 컨펌용 전체 미리보기 한 장
"""
import glob
import json
import os

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(SKILL_DIR, ".env")
DECKS_DIR = os.path.join(SKILL_DIR, "decks")
STATE_DIR = os.path.join(SKILL_DIR, "state")


def load_env(path=None):
    env = {}
    with open(path or ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def state_path(name):
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, name)


def load_deck(slug_or_dir):
    d = slug_or_dir if os.path.isdir(slug_or_dir) else os.path.join(DECKS_DIR, slug_or_dir)
    with open(os.path.join(d, "deck.json")) as f:
        deck = json.load(f)
    with open(os.path.join(d, "captions.json")) as f:
        deck["captions"] = json.load(f)
    deck.setdefault("slug", os.path.basename(os.path.normpath(d)))
    deck["dir"] = d
    deck["slides"] = sorted(glob.glob(os.path.join(d, "slides", "slide-*.jpg")))
    deck["preview"] = os.path.join(d, "preview.png")
    return deck


def all_decks():
    return [load_deck(os.path.dirname(p)) for p in sorted(glob.glob(os.path.join(DECKS_DIR, "*", "deck.json")))]
