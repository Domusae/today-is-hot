from datetime import datetime

from src.card import build_attachment, build_payload
from src.config import Region
from src.detector import detect_heat_warnings, summarize_temps
from src.state import filter_new, mark, prune

DAEJEON = Region(name="대전", stn_id="133", nx=67, ny=100, keywords=("대전", "충남"))


def warn(title, tm_fc="202607291100", tm_seq="1"):
    return {"title": title, "tmFc": tm_fc, "tmSeq": tm_seq, "stnId": "133"}


class TestDetectHeatWarnings:
    def test_picks_up_advisory_for_region(self):
        items = [warn("[기상특보] 대전, 세종, 충남 폭염주의보 발표")]
        events = detect_heat_warnings(items, DAEJEON)
        assert len(events) == 1
        assert events[0].kind == "폭염주의보"
        assert events[0].action == "발표"

    def test_picks_up_warning_level(self):
        events = detect_heat_warnings([warn("[기상특보] 대전 폭염경보 발표")], DAEJEON)
        assert events[0].kind == "폭염경보"

    def test_detects_release(self):
        events = detect_heat_warnings([warn("[기상특보] 대전 폭염주의보 해제")], DAEJEON)
        assert events[0].is_release

    def test_ignores_other_regions(self):
        assert detect_heat_warnings([warn("[기상특보] 부산 폭염경보 발표")], DAEJEON) == []

    def test_ignores_other_warning_types(self):
        assert detect_heat_warnings([warn("[기상특보] 대전 호우주의보 발표")], DAEJEON) == []

    def test_key_is_stable_and_unique(self):
        a = detect_heat_warnings([warn("[기상특보] 대전 폭염경보 발표", tm_seq="1")], DAEJEON)[0]
        b = detect_heat_warnings([warn("[기상특보] 대전 폭염경보 발표", tm_seq="2")], DAEJEON)[0]
        assert a.key != b.key
        c = detect_heat_warnings([warn("[기상특보] 대전 폭염경보 발표", tm_seq="1")], DAEJEON)[0]
        assert a.key == c.key


def fcst(date, time, category, value):
    return {"fcstDate": date, "fcstTime": time, "category": category, "fcstValue": value}


class TestSummarizeTemps:
    def test_reads_daily_max_and_min(self):
        items = [
            fcst("20260729", "1500", "TMX", "36.0"),
            fcst("20260729", "0600", "TMN", "26.0"),
        ]
        temps = summarize_temps(items, datetime(2026, 7, 29, 18, 0))
        assert temps == {"today_max": 36.0, "today_min": 26.0}

    def test_ignores_other_days(self):
        items = [fcst("20260730", "1500", "TMX", "40.0")]
        assert summarize_temps(items, datetime(2026, 7, 29, 18, 0)) == {}

    def test_tolerates_missing_values(self):
        items = [fcst("20260729", "1500", "TMP", "33")]
        assert summarize_temps(items, datetime(2026, 7, 29, 18, 0)) == {}


class TestState:
    def test_filter_new_removes_already_sent(self):
        events = detect_heat_warnings([warn("[기상특보] 대전 폭염경보 발표")], DAEJEON)
        sent = mark(events, {})
        assert filter_new(events, sent) == []

    def test_prune_drops_old_keys(self):
        sent = {"old": "2026-07-01T00:00:00", "new": "2026-07-29T00:00:00"}
        kept = prune(sent, datetime(2026, 7, 29, 12, 0))
        assert "old" not in kept and "new" in kept


class TestCard:
    def test_warning_card_is_red_and_has_guide(self):
        event = detect_heat_warnings([warn("[기상특보] 대전 폭염경보 발표")], DAEJEON)[0]
        attachment = build_attachment(event)
        assert attachment["color"] == "#D0021B"
        assert "이렇게 하세요" in attachment["text"]

    def test_release_card_is_green(self):
        event = detect_heat_warnings([warn("[기상특보] 대전 폭염주의보 해제")], DAEJEON)[0]
        assert build_attachment(event)["color"] == "#2FA84F"

    def test_payload_bundles_all_events(self):
        events = detect_heat_warnings(
            [
                warn("[기상특보] 대전 폭염경보 발표", tm_seq="1"),
                warn("[기상특보] 충남 폭염주의보 발표", tm_seq="2"),
            ],
            DAEJEON,
        )
        payload = build_payload(events, "봇", ":sunny:")
        assert len(payload["attachments"]) == 2
        assert payload["username"] == "봇"
