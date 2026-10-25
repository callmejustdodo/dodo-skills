"""클라이언트 통화 녹음을 ElevenLabs Scribe v2로 화자 분리 전사한다.

    python3 transcribe.py <audio> --out-dir <run_dir> [--lang kor] [--speakers 2]
                          [--keyterms "회사명,제품명,홍길동"] [--roles]

run_dir에 남기는 것:
    source.<ext>      원본 사본 (iCloud dataless 파일도 여기서 내려받아짐)
    raw.json          Scribe 응답 (단어별 시각·화자·logprob)
    transcript.json   화자 턴 목록 {"segments": [{start, end, speaker, text}]}
    meta.json         길이·언어·화자 수·예상 비용·신뢰도 낮은 단어

API 키는 셸의 ELEVENLABS_API_KEY에서 읽는다. 키를 출력하거나 파일에 쓰지 않는다.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

RATE_PER_MIN = 0.40 / 60  # scribe_v2 ≈ $0.40/hr (요금제마다 다름 — 대시보드가 기준)
KEYTERMS_SURCHARGE = 0.20
ROLES_SURCHARGE = 0.10
LANG_MAP = {"ko": "kor", "en": "eng", "ja": "jpn", "zh": "zho"}
SPLIT_GAP_SEC = 1.5  # 같은 화자라도 이만큼 쉬면 턴을 나눈다 — 긴 독백도 타임스탬프가 촘촘해진다
MAX_TURN_SEC = 45  # 이보다 길어진 턴은 다음 문장 끝에서 나눈다
SENTENCE_END = (".", "?", "!")


def build_segments(words):
    """단어 목록을 턴으로 묶는다.

    화자가 바뀌거나, 같은 화자라도 SPLIT_GAP_SEC 이상 쉬거나, 턴이 MAX_TURN_SEC를 넘긴 뒤 문장이
    끝나면 새 턴을 연다. 오디오 이벤트(웃음 등)와 공백은 그 자리 턴에 남기지만 턴의 끝 시각은
    마지막 단어 기준이다. 시각이 빠진 토큰은 바로 앞 시각을 이어 쓴다.
    """
    segments, cur, clock = [], None, 0.0

    def close():
        text = "".join(cur["parts"]).strip() if cur else ""
        if text:
            end = cur["end"] if cur["end"] is not None else cur["start"]
            segments.append({"start": cur["start"], "end": end, "speaker": cur["speaker"] or "speaker_unknown", "text": text})

    for w in words:
        kind = w.get("type")
        if kind not in ("word", "spacing", "audio_event"):
            continue
        start = w["start"] if w.get("start") is not None else clock
        end = w["end"] if w.get("end") is not None else start
        clock = max(clock, end)
        if kind == "word":
            spk = w.get("speaker_id")
            if cur is None:
                cur = {"speaker": spk, "start": start, "end": None, "parts": []}
            elif cur["speaker"] is None:  # 앞에 오디오 이벤트만 있던 턴
                cur["speaker"] = spk
            else:
                changed = spk is not None and spk != cur["speaker"]
                paused = cur["end"] is not None and start - cur["end"] >= SPLIT_GAP_SEC
                too_long = start - cur["start"] >= MAX_TURN_SEC and "".join(cur["parts"]).rstrip().endswith(SENTENCE_END)
                if changed or paused or too_long:
                    close()
                    cur = {"speaker": spk or cur["speaker"], "start": start, "end": None, "parts": []}
            cur["end"] = end
        elif cur is None:
            cur = {"speaker": None, "start": start, "end": None, "parts": []}
        cur["parts"].append(w["text"])
    close()
    return segments


def low_confidence(words, limit=30, below=-0.5):
    """logprob가 낮은 단어들 — 고유명사 오인식 후보. 대부분의 단어는 -0.2 위에 있다."""
    scored = [w for w in words if w.get("type") == "word" and (w.get("logprob") or 0) < below]
    scored.sort(key=lambda w: w["logprob"])
    return [{"start": w.get("start"), "text": w["text"], "logprob": round(w["logprob"], 2)} for w in scored[:limit]]


def probe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def estimate_cost(duration_sec, keyterms, roles):
    if not duration_sec:
        return None
    factor = 1 + (KEYTERMS_SURCHARGE if keyterms else 0) + (ROLES_SURCHARGE if roles else 0)
    return round(duration_sec / 60 * RATE_PER_MIN * factor, 4)


def parse_keyterms(values):
    terms = []
    for v in values or []:
        terms += [t.strip() for t in v.split(",") if t.strip()]
    bad = [t for t in terms if len(t) >= 50 or any(c in t for c in "<>{}[]\\")]
    if bad:
        sys.exit(f"keyterms는 50자 미만이고 <>{{}}[]\\ 문자가 없어야 해요: {bad}")
    return list(dict.fromkeys(terms))[:1000]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lang", default="kor", help="ISO 639-1/3 언어 코드 (기본 kor)")
    ap.add_argument("--speakers", type=int, default=2, help="통화 참여 인원 상한 (기본 2)")
    ap.add_argument("--keyterms", action="append", help="쉼표로 구분한 이름·회사·제품명. 여러 번 줄 수 있음")
    ap.add_argument("--roles", action="store_true", help="agent/customer 역할 자동 판별 (+10%%, 2인 통화용)")
    args = ap.parse_args()

    if not os.path.isfile(args.audio):
        sys.exit(f"녹음 파일이 없어요: {args.audio}")
    if args.roles and args.speakers != 2:
        sys.exit("--roles는 2인 통화에서만 써요. 3명 이상이면 --roles 없이 실행하세요.")
    if not os.environ.get("ELEVENLABS_API_KEY"):
        sys.exit("ELEVENLABS_API_KEY가 셸에 없어요. export ELEVENLABS_API_KEY=... 후 다시 실행하세요.")
    try:
        from elevenlabs import ElevenLabs
        from elevenlabs.core.api_error import ApiError
    except ImportError:
        sys.exit("elevenlabs SDK가 없어요: python3 -m pip install --user elevenlabs")

    os.makedirs(args.out_dir, exist_ok=True)
    ext = os.path.splitext(args.audio)[1].lower() or ".audio"
    source = os.path.join(args.out_dir, "source" + ext)
    if os.path.abspath(args.audio) != os.path.abspath(source):
        shutil.copy2(args.audio, source)

    keyterms = parse_keyterms(args.keyterms)
    lang = LANG_MAP.get(args.lang, args.lang)
    duration = probe_duration(source)
    est = estimate_cost(duration, keyterms, args.roles)
    if duration:
        print(f"길이 {duration / 60:.1f}분 · 예상 비용 ${est:.3f}")

    kwargs = {
        "model_id": "scribe_v2",
        "diarize": True,
        "num_speakers": args.speakers,
        "timestamps_granularity": "word",
        "tag_audio_events": True,
        "language_code": lang,
    }
    if keyterms:
        kwargs["keyterms"] = keyterms
    if args.roles:
        kwargs["detect_speaker_roles"] = True

    # 긴 통화는 서버 처리에 몇 분 걸린다. SDK 기본 타임아웃(240초)보다 넉넉히 준다.
    client = ElevenLabs(timeout=1200)
    t0 = time.time()
    try:
        with open(source, "rb") as f:
            result = client.speech_to_text.convert(file=f, **kwargs)
    except ApiError as e:
        sys.exit(f"Scribe 오류 {e.status_code}: {e.body}")
    except Exception as e:  # 네트워크·타임아웃 — run 폴더는 남아 있으니 그대로 다시 실행하면 된다
        sys.exit(f"Scribe 호출 실패 ({type(e).__name__}): {e}")
    elapsed = time.time() - t0

    words = [
        {
            "text": w.text,
            "start": w.start,
            "end": w.end,
            "type": w.type,
            "speaker_id": w.speaker_id,
            "logprob": w.logprob,
        }
        for w in (result.words or [])
    ]
    raw = {
        "text": result.text,
        "language_code": result.language_code,
        "language_probability": result.language_probability,
        "audio_duration_secs": result.audio_duration_secs,
        "transcription_id": result.transcription_id,
        "words": words,
    }
    with open(os.path.join(args.out_dir, "raw.json"), "w") as o:
        json.dump(raw, o, ensure_ascii=False, indent=2)

    segments = build_segments(words)
    with open(os.path.join(args.out_dir, "transcript.json"), "w") as o:
        json.dump({"segments": segments}, o, ensure_ascii=False, indent=2)

    duration = result.audio_duration_secs or duration
    speakers = sorted({s["speaker"] for s in segments})
    meta = {
        "source": os.path.basename(args.audio),
        "duration_sec": duration,
        "language_code": result.language_code,
        "language_probability": result.language_probability,
        "speakers": speakers,
        "segments": len(segments),
        "words": sum(1 for w in words if w["type"] == "word"),
        "elapsed_sec": round(elapsed, 1),
        "params": {k: v for k, v in kwargs.items() if k != "model_id"},
        "cost_usd": estimate_cost(duration, keyterms, args.roles),
        "low_confidence": low_confidence(words),
    }
    with open(os.path.join(args.out_dir, "meta.json"), "w") as o:
        json.dump(meta, o, ensure_ascii=False, indent=2)

    if not segments:
        sys.exit("전사된 문장이 없어요. 언어(--lang)가 맞는지, 녹음에 말소리가 있는지 확인하세요. 응답은 raw.json에 있어요.")
    cost = f"${meta['cost_usd']:.3f}" if meta["cost_usd"] is not None else "알 수 없음"
    print(f"scribe_v2 {elapsed:.0f}초 · 턴 {len(segments)}개 · 화자 {', '.join(speakers)} · "
          f"언어 {result.language_code} ({result.language_probability or 0:.2f}) · 비용 ≈ {cost}")


if __name__ == "__main__":
    main()
