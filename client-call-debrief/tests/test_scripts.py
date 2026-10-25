"""API 호출 없이 스크립트 로직을 검증한다.

    python3 -m unittest discover -s client-call-debrief/tests

fixtures/sample_transcript.json은 fixtures/sample_call_script.tsv(가상 세일즈 통화)를
macOS say로 읽힌 녹음을 Scribe v2로 전사한 실제 결과다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)

import analyze_call  # noqa: E402
import transcribe  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "sample_transcript.json")


def read(path):
    with open(path) as f:
        return f.read()


def load(path):
    return json.loads(read(path))


def word(text, start, end, spk, kind="word"):
    return {"text": text, "start": start, "end": end, "type": kind, "speaker_id": spk}


class BuildSegmentsTest(unittest.TestCase):
    def test_splits_on_speaker_change(self):
        words = [
            word("안녕하세요", 0.0, 0.5, "speaker_0"), word(" ", 0.5, 0.6, "speaker_0", "spacing"),
            word("대표님", 0.6, 1.0, "speaker_0"),
            word(" ", 1.0, 1.4, "speaker_1", "spacing"),
            word("네", 1.4, 1.6, "speaker_1"),
        ]
        segs = transcribe.build_segments(words)
        self.assertEqual([s["speaker"] for s in segs], ["speaker_0", "speaker_1"])
        self.assertEqual(segs[0]["text"], "안녕하세요 대표님")
        self.assertEqual((segs[1]["start"], segs[1]["end"]), (1.4, 1.6))

    def test_leading_audio_event_joins_first_speaker(self):
        words = [word("(음악)", 0.0, 2.0, None, "audio_event"), word("여보세요", 2.1, 2.5, "speaker_0")]
        segs = transcribe.build_segments(words)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["speaker"], "speaker_0")
        self.assertEqual(segs[0]["start"], 0.0)
        self.assertIn("(음악)", segs[0]["text"])

    def test_audio_event_stays_in_current_turn(self):
        words = [word("좋네요", 0.0, 0.4, "speaker_1"), word("(웃음)", 0.4, 0.9, None, "audio_event"),
                 word("그럼", 1.0, 1.2, "speaker_0")]
        segs = transcribe.build_segments(words)
        self.assertEqual([s["speaker"] for s in segs], ["speaker_1", "speaker_0"])
        self.assertIn("(웃음)", segs[0]["text"])

    def test_empty(self):
        self.assertEqual(transcribe.build_segments([]), [])

    def test_same_speaker_pause_starts_new_turn(self):
        words = [word("네.", 0.0, 1.0, "speaker_0"), word(" ", 1.0, 3.0, "speaker_0", "spacing"),
                 word("그리고요", 3.0, 3.5, "speaker_0")]
        segs = transcribe.build_segments(words)
        self.assertEqual([(s["speaker"], s["start"]) for s in segs], [("speaker_0", 0.0), ("speaker_0", 3.0)])

    def test_long_monologue_splits_at_sentence_end(self):
        words = []
        for i in range(60):
            words.append(word("말" + ("." if i % 10 == 9 else ""), float(i), i + 1.0, "speaker_0"))
            words.append(word(" ", i + 1.0, i + 1.0, "speaker_0", "spacing"))
        segs = transcribe.build_segments(words)
        self.assertEqual([s["start"] for s in segs], [0.0, 50.0])
        self.assertTrue(segs[0]["text"].endswith("."))

    def test_turn_end_ignores_trailing_spacing(self):
        words = [word("가격은 200만 원입니다.", 0.0, 1.0, "speaker_0"), word(" ", 1.0, 4.0, "speaker_1", "spacing"),
                 word("글쎄요", 4.0, 4.5, "speaker_1")]
        segs = transcribe.build_segments(words)
        self.assertEqual(segs[0]["end"], 1.0)
        pauses = analyze_call.compute(segs, {"speaker_0"})["pauses"]
        self.assertEqual([p["sec"] for p in pauses], [3.0])

    def test_missing_times_continue_from_previous(self):
        words = [word("네", 1799.0, 1800.0, "speaker_0"), word("음", None, None, "speaker_1")]
        segs = transcribe.build_segments(words)
        self.assertEqual(segs[1]["start"], 1800.0)
        self.assertEqual(segs[1]["end"], 1800.0)

    def test_unknown_speaker_label_is_shell_safe(self):
        segs = transcribe.build_segments([word("여보세요", 0.0, 0.5, None)])
        self.assertEqual(segs[0]["speaker"], "speaker_unknown")

    def test_low_confidence_keeps_only_unsure_words(self):
        words = [dict(word("공동대표님", 1.0, 1.5, "s"), logprob=-0.05),
                 dict(word("I", 0.7, 0.9, "s"), logprob=-0.75),
                 dict(word("4", 24.7, 24.8, "s"), logprob=-1.02),
                 dict(word(" ", 0.9, 1.0, "s", "spacing"), logprob=-3.0)]
        self.assertEqual([w["text"] for w in transcribe.low_confidence(words)], ["4", "I"])


class KeytermsTest(unittest.TestCase):
    def test_splits_and_dedupes(self):
        self.assertEqual(transcribe.parse_keyterms(["A사, 홍길동", "홍길동,CRM"]), ["A사", "홍길동", "CRM"])

    def test_rejects_unsupported(self):
        with self.assertRaises(SystemExit):
            transcribe.parse_keyterms(["[내부]"])

    def test_cost_surcharges(self):
        self.assertAlmostEqual(transcribe.estimate_cost(3600, [], False), 0.40, places=4)
        self.assertAlmostEqual(transcribe.estimate_cost(3600, ["x"], True), 0.52, places=4)
        self.assertIsNone(transcribe.estimate_cost(None, [], False))


class TranscribeMainTest(unittest.TestCase):
    """가짜 elevenlabs 모듈로 main()이 만드는 요청과 산출물을 확인한다."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.audio = os.path.join(self.dir, "call.m4a")
        with open(self.audio, "wb") as f:
            f.write(b"not really audio")
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self.dir)

    def fake_sdk(self, words):
        calls = self.calls

        class ApiError(Exception):
            status_code, body = 401, "bad key"

        class ElevenLabs:
            def __init__(self, timeout=None):
                calls.append({"timeout": timeout})
                self.speech_to_text = self

            def convert(self, file, **kwargs):
                calls[-1].update(kwargs)
                return types.SimpleNamespace(
                    text="".join(w[0] for w in words), language_code="kor", language_probability=0.99,
                    audio_duration_secs=60.0, transcription_id="t1",
                    words=[types.SimpleNamespace(text=t, start=s, end=e, type=k, speaker_id=spk, logprob=-0.01)
                           for t, s, e, k, spk in words])

        root = types.ModuleType("elevenlabs")
        root.ElevenLabs = ElevenLabs
        core = types.ModuleType("elevenlabs.core")
        err = types.ModuleType("elevenlabs.core.api_error")
        err.ApiError = ApiError
        return {"elevenlabs": root, "elevenlabs.core": core, "elevenlabs.core.api_error": err}

    def run_main(self, words, *args):
        out = os.path.join(self.dir, "run")
        argv = ["transcribe.py", self.audio, "--out-dir", out, *args]
        with mock.patch.dict(sys.modules, self.fake_sdk(words)), \
                mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test"}), \
                mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout"):
            transcribe.main()
        return out

    def test_builds_request_and_writes_outputs(self):
        words = [("안녕하세요", 0.0, 0.5, "word", "agent"), (" ", 0.5, 0.6, "spacing", "agent"),
                 ("네", 1.0, 1.2, "word", "customer")]
        out = self.run_main(words, "--roles", "--keyterms", "OO학원,김대표", "--lang", "ko")
        call = self.calls[0]
        self.assertEqual(call["timeout"], 1200)
        self.assertEqual((call["model_id"], call["language_code"], call["num_speakers"]), ("scribe_v2", "kor", 2))
        self.assertTrue(call["diarize"] and call["detect_speaker_roles"] and call["tag_audio_events"])
        self.assertEqual(call["keyterms"], ["OO학원", "김대표"])
        for name in ("source.m4a", "raw.json", "transcript.json", "meta.json"):
            self.assertTrue(os.path.isfile(os.path.join(out, name)), name)
        meta = load(os.path.join(out, "meta.json"))
        self.assertEqual(meta["speakers"], ["agent", "customer"])
        self.assertAlmostEqual(meta["cost_usd"], round(60 / 60 * transcribe.RATE_PER_MIN * 1.3, 4))
        self.assertNotIn("test", json.dumps(meta))  # API 키가 산출물에 남지 않는다

    def test_roles_need_two_speakers(self):
        with self.assertRaises(SystemExit):
            self.run_main([], "--roles", "--speakers", "3")
        self.assertEqual(self.calls, [])

    def test_empty_result_exits_nonzero(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_main([])
        self.assertIn("전사된 문장이 없어요", str(cm.exception.code))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "run", "raw.json")))


class ComputeTest(unittest.TestCase):
    def setUp(self):
        self.segments = load(FIXTURE)["segments"]

    def test_talk_share_and_questions(self):
        sig = analyze_call.compute(self.segments, {"speaker_0"})
        self.assertEqual(sig["talk_share"]["ours"] + sig["talk_share"]["theirs"], 100)
        self.assertEqual(sig["questions"]["ours"], 4)
        self.assertEqual(sig["questions"]["theirs"], 0)

    def test_pause_after_price_is_longest(self):
        sig = analyze_call.compute(self.segments, {"speaker_0"})
        top = sig["pauses"][0]
        self.assertGreaterEqual(top["sec"], 3.0)
        self.assertIn("200만 원", top["after_us"])
        self.assertIn("글쎄요", top["they_said"])

    def test_cues_only_from_client(self):
        sig = analyze_call.compute(self.segments, {"speaker_0"})
        self.assertTrue(all(c["speaker"] == "speaker_1" for c in sig["cues"]))
        cats = set(sig["cue_counts"])
        for expected in ("가격·예산", "효과·확신", "의사결정 구조", "신뢰·과거 경험", "유보 표현"):
            self.assertIn(expected, cats)

    def test_one_cue_per_category_per_turn(self):
        segs = [{"start": 0, "end": 1, "speaker": "c", "text": "비싸고 비용도 예산도 부담돼요"}]
        sig = analyze_call.compute(segs, {"me"})
        self.assertEqual(sig["cue_counts"], {"가격·예산": 1})

    def test_pause_keeps_end_of_our_line(self):
        ours = "저희 프로그램은 상담 녹음 요약, 후속 연락 자동화, 주간 리포트까지 포함되어 있고 첫 주에 바로 세팅해 드리며 " \
               "비용은 월 200만 원입니다."
        segs = [{"start": 0, "end": 10, "speaker": "me", "text": ours},
                {"start": 14, "end": 15, "speaker": "c", "text": "글쎄요."}]
        after_us = analyze_call.compute(segs, {"me"})["pauses"][0]["after_us"]
        self.assertTrue(after_us.endswith("월 200만 원입니다."))
        self.assertLessEqual(len(after_us), 100)

    def test_sentence_keeps_decimals(self):
        text = "효과가 1.5배는 될까요? 글쎄요."
        self.assertEqual(analyze_call.sentence_at(text, text.find("될까")), "효과가 1.5배는 될까요?")

    def test_cue_terms_avoid_common_false_hits(self):
        segs = [{"start": 0, "end": 1, "speaker": "c", "text": "세 명 이상의 직원이 있어요. 대표님 말씀 잘 들었어요."}]
        self.assertNotIn("의사결정 구조", analyze_call.compute(segs, {"me"})["cue_counts"])

    def test_ts_format(self):
        self.assertEqual(analyze_call.ts(65.4), "01:05")
        self.assertEqual(analyze_call.ts(3725), "1:02:05")


class AnalyzeCliTest(unittest.TestCase):
    def setUp(self):
        self.run = tempfile.mkdtemp()
        shutil.copy(FIXTURE, os.path.join(self.run, "transcript.json"))

    def tearDown(self):
        shutil.rmtree(self.run)

    def cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "analyze_call.py"), self.run, *args],
                              capture_output=True, text=True)

    def test_writes_named_outputs(self):
        r = self.cli("--me", "speaker_0", "--name", "speaker_0=도현", "--name", "speaker_1=김대표")
        self.assertEqual(r.returncode, 0, r.stderr)
        transcript = read(os.path.join(self.run, "transcript.md"))
        self.assertTrue(transcript.startswith("[00:00] 도현: "))
        self.assertIn("김대표: 음, 글쎄요.", transcript)
        signals = read(os.path.join(self.run, "signals.md"))
        self.assertIn("발화 비중", signals)
        self.assertIn("김대표:", signals)
        sig = load(os.path.join(self.run, "signals.json"))
        self.assertEqual(sig["ours"], ["speaker_0"])

    def test_requires_me_without_roles(self):
        r = self.cli()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--me", r.stderr)

    def test_rejects_unknown_speaker(self):
        r = self.cli("--me", "speaker_9")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("speaker_9", r.stderr)

    def test_empty_transcript_fails_clearly(self):
        with open(os.path.join(self.run, "transcript.json"), "w") as f:
            json.dump({"segments": []}, f)
        r = self.cli("--me", "speaker_0")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("턴이 없어요", r.stderr)

    def test_role_labels_default_me_to_agent(self):
        path = os.path.join(self.run, "transcript.json")
        data = load(path)
        for s in data["segments"]:
            s["speaker"] = {"speaker_0": "agent", "speaker_1": "customer"}[s["speaker"]]
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)
        r = self.cli("--name", "agent=도현")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(load(os.path.join(self.run, "signals.json"))["ours"], ["agent"])


if __name__ == "__main__":
    unittest.main()
