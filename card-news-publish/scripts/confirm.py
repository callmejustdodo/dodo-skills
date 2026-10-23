"""덱 컨펌 요청을 지금 바로 Slack에 보낸다. 버튼 처리는 실행 중인 bot.py가 맡는다.

    python confirm.py <slug> [--channel C123] [--thread 1712345678.000100]
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slack_sdk import WebClient  # noqa: E402

import deck as decklib  # noqa: E402
import publisher  # noqa: E402
import slack_io  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("slug")
ap.add_argument("--channel")
ap.add_argument("--thread")
args = ap.parse_args()

env = decklib.load_env()
deck = decklib.load_deck(args.slug)
errs = publisher.validate_assets(deck)
if errs:
    sys.exit("덱 점검 실패: " + " / ".join(errs))
if not slack_io.bot_running():
    print("주의: bot.py가 꺼져 있어서 버튼을 눌러도 처리되지 않아요. 먼저 봇을 실행해 주세요.")
client = WebClient(token=env["SLACK_BOT_TOKEN"])
file_id = slack_io.preview_file_id(client, deck)
time.sleep(3)  # 방금 올린 미리보기를 Slack이 처리할 시간
ts = slack_io.post_confirm(client, deck, args.channel or env["SLACK_CHANNEL"], env["SLACK_ALLOWED_USERS"].split(",")[0], file_id, args.thread)
print("sent:", ts)
