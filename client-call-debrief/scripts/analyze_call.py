"""전사된 통화에 실명을 붙이고, 허들 분석의 출발점이 될 통화 지표를 뽑는다.

    python3 analyze_call.py <run_dir> --me speaker_0 [--me speaker_2]
                            [--name speaker_0=도현 --name speaker_1=김대표]

run_dir/transcript.json을 읽어 다음을 쓴다:
    transcript.md   [MM:SS] 이름: 발언 — 옵시디언 전사 노트 본문
    signals.json    발화 비중, 최장 독백, 질문 수, 고객 응답 지연, 고객 발언 속 허들 단서
    signals.md      위 지표를 노트에 붙일 수 있는 마크다운으로

지표는 '어디를 다시 읽을지' 알려주는 포인터다. 허들 판단은 반드시 원문 맥락을 읽고 내린다.
API 호출이 없어 이름 매핑을 고친 뒤 몇 번이든 다시 돌려도 된다.
"""
import argparse
import json
import os
import re
import sys

# 고객 쪽 발언에서만 찾는다. 단어가 있다고 허들이 있는 게 아니고, 없다고 허들이 없는 것도 아니다.
CUES = {
    "가격·예산": ["비싸", "비용", "예산", "가격", "금액", "할인", "견적", "부담스럽", "부담되", "투자 대비"],
    "시점·우선순위": ["나중에", "다음 달", "다음달", "다음 분기", "내년", "아직은", "당장은", "바빠", "바쁘", "여유가", "시기가"],
    "의사결정 구조": ["상의해", "상의를", "상의드", "상의할", "대표님이랑", "대표님과", "대표님께", "대표님한테", "윗선", "윗분", "내부적으로", "보고드", "보고해야", "결재", "팀장님", "이사님", "논의해"],
    "효과·확신": ["효과", "될까", "되려나", "보장", "확신", "사례", "레퍼런스", "결과가", "성과"],
    "신뢰·과거 경험": ["해봤는데", "해 봤는데", "써봤는데", "써 봤는데", "다른 업체", "다른 곳", "다른 데", "실패", "별로였"],
    "실행 부담": ["시간이 없", "인력", "리소스", "손이 많이", "따라갈", "복잡", "번거", "운영할 사람"],
    "유보 표현": ["글쎄", "고민해", "생각해 볼", "생각해볼", "생각해 보", "생각해보", "검토해", "모르겠", "애매", "다시 연락"],
}
PAUSE_MIN_SEC = 1.5
MD_PAUSES, MD_CUES = 10, 40  # signals.md에 싣는 개수. 전체 목록은 signals.json
BOUNDARY = re.compile(r"[.?!](?=\s|$)")  # "1.5배"의 점은 문장 끝이 아니다


def ts(sec):
    sec = int(sec or 0)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def clip(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def clip_tail(text, n):
    """끝부분을 남긴다 — 침묵 직전에 우리가 한 말이 중요하다."""
    text = " ".join(text.split())
    return text if len(text) <= n else "…" + text[-(n - 1):]


def sentence_at(text, pos):
    start, end = 0, len(text)
    for m in BOUNDARY.finditer(text):
        if m.end() <= pos:
            start = m.end()
        else:
            end = m.end()
            break
    return text[start:end].strip()


def compute(segments, ours):
    by_speaker, sides = {}, {"ours": 0.0, "theirs": 0.0}
    longest = {"ours": None, "theirs": None}
    questions = {"ours": 0, "theirs": 0}
    for s in segments:
        dur = max(0.0, (s["end"] or 0) - (s["start"] or 0))
        side = "ours" if s["speaker"] in ours else "theirs"
        by_speaker[s["speaker"]] = by_speaker.get(s["speaker"], 0.0) + dur
        sides[side] += dur
        questions[side] += s["text"].count("?")
        if longest[side] is None or dur > longest[side]["sec"]:
            longest[side] = {"sec": round(dur, 1), "at": ts(s["start"]), "speaker": s["speaker"], "text": clip(s["text"], 120)}

    total = sum(sides.values()) or 1.0
    pauses = []
    for prev, cur in zip(segments, segments[1:]):
        if prev["speaker"] in ours and cur["speaker"] not in ours:
            gap = (cur["start"] or 0) - (prev["end"] or 0)
            if gap >= PAUSE_MIN_SEC:
                pauses.append({
                    "sec": round(gap, 1),
                    "at": ts(cur["start"]),
                    "after_us": clip_tail(prev["text"], 100),
                    "they_said": clip(cur["text"], 100),
                })
    pauses.sort(key=lambda p: -p["sec"])

    cues = []
    for s in segments:
        if s["speaker"] in ours:
            continue
        for category, terms in CUES.items():
            for term in terms:
                pos = s["text"].find(term)
                if pos != -1:
                    cues.append({"at": ts(s["start"]), "speaker": s["speaker"], "category": category,
                                 "term": term, "sentence": clip(sentence_at(s["text"], pos), 140)})
                    break  # 한 턴에서 카테고리당 한 번만

    return {
        "duration_sec": round(max((s["end"] or 0) for s in segments), 1) if segments else 0,
        "talk_share": {"ours": round(sides["ours"] / total * 100), "theirs": round(sides["theirs"] / total * 100)},
        "talk_sec_by_speaker": {k: round(v, 1) for k, v in by_speaker.items()},
        "longest_turn": longest,
        "questions": questions,
        "pauses": pauses,
        "cues": cues,
        "cue_counts": {c: sum(1 for x in cues if x["category"] == c) for c in CUES if any(x["category"] == c for x in cues)},
    }


def render_signals(sig, names):
    n = lambda spk: names.get(spk, spk)
    lines = [
        f"- 발화 비중: 우리 {sig['talk_share']['ours']}% · 고객 {sig['talk_share']['theirs']}%",
        f"- 질문 수: 우리 {sig['questions']['ours']}개 · 고객 {sig['questions']['theirs']}개",
    ]
    for side, label in (("ours", "우리"), ("theirs", "고객")):
        t = sig["longest_turn"][side]
        if t:
            lines.append(f"- 최장 발언({label}): {t['sec']}초 [{t['at']}] {n(t['speaker'])} — \"{t['text']}\"")
    if sig["pauses"]:
        lines += ["", f"**고객 응답이 {PAUSE_MIN_SEC}초 이상 늦어진 순간** (긴 순서)", ""]
        for p in sig["pauses"][:MD_PAUSES]:
            lines.append(f"- [{p['at']}] {p['sec']}초 — 우리: \"{p['after_us']}\" → 고객: \"{p['they_said']}\"")
        if len(sig["pauses"]) > MD_PAUSES:
            lines.append(f"- 외 {len(sig['pauses']) - MD_PAUSES}곳 — signals.json")
    if sig["cues"]:
        lines += ["", "**고객 발언 속 허들 단서 (맥락 확인 필요)**", ""]
        for c in sig["cues"][:MD_CUES]:
            lines.append(f"- [{c['at']}] {c['category']} `{c['term']}` — {n(c['speaker'])}: \"{c['sentence']}\"")
        if len(sig["cues"]) > MD_CUES:
            lines.append(f"- 외 {len(sig['cues']) - MD_CUES}개 — signals.json")
    return "\n".join(lines) + "\n"


def render_transcript(segments, names):
    return "\n\n".join(f"[{ts(s['start'])}] {names.get(s['speaker'], s['speaker'])}: {s['text']}" for s in segments) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--me", action="append", default=[], help="우리 쪽 화자 id (여러 명이면 반복)")
    ap.add_argument("--name", action="append", default=[], help="speaker_0=도현 형식의 실명 매핑")
    args = ap.parse_args()

    path = os.path.join(args.run_dir, "transcript.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} 이 없어요. transcribe.py를 먼저 실행하세요.")
    with open(path) as f:
        segments = json.load(f)["segments"]
    if not segments:
        sys.exit("transcript.json에 턴이 없어요. 전사 결과(raw.json)와 언어 설정을 확인하세요.")
    speakers = {s["speaker"] for s in segments}

    names = {}
    for pair in args.name:
        spk, _, name = pair.partition("=")
        if not name:
            sys.exit(f"--name은 speaker_0=이름 형식이어야 해요: {pair}")
        names[spk.strip()] = name.strip()
    ours = set(args.me) or ({"agent"} if "agent" in speakers else set())
    if not ours:
        sys.exit(f"--me로 우리 쪽 화자를 지정하세요. 이 통화의 화자: {', '.join(sorted(speakers))}")
    unknown = (ours | set(names)) - speakers
    if unknown:
        sys.exit(f"전사에 없는 화자 id: {', '.join(sorted(unknown))} (있는 화자: {', '.join(sorted(speakers))})")

    sig = compute(segments, ours)
    sig["ours"], sig["names"] = sorted(ours), names
    with open(os.path.join(args.run_dir, "signals.json"), "w") as o:
        json.dump(sig, o, ensure_ascii=False, indent=2)
    with open(os.path.join(args.run_dir, "signals.md"), "w") as o:
        o.write(render_signals(sig, names))
    with open(os.path.join(args.run_dir, "transcript.md"), "w") as o:
        o.write(render_transcript(segments, names))

    print(f"우리 {sig['talk_share']['ours']}% · 고객 {sig['talk_share']['theirs']}% · "
          f"응답 지연 {len(sig['pauses'])}곳 · 허들 단서 {len(sig['cues'])}개 {sig['cue_counts']}")


if __name__ == "__main__":
    main()
