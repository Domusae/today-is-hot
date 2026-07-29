"""probe.py로 확인한 실제 응답 형태를 기준으로 작성했다."""
from datetime import datetime

from src.card import build_attachment, build_payload
from src.config import Region
from src.card import _forecast_level
from src.detector import (
    build_events,
    current_warnings,
    forecast_event,
    parse_segments,
    recent_releases,
    summarize_temps,
)
from src.state import filter_new, mark, prune

GANGNAM = Region(name="서울 강남구", stn_id="108", nx=61, ny=125)
NOW = datetime(2026, 7, 29, 9, 0)


def warn(tm_fc, body, seq=1):
    """실제 제목 형식 그대로 만든다."""
    return {
        "stnId": "108",
        "tmFc": int(tm_fc),
        "tmSeq": seq,
        "title": f"[특보] 제07-{seq}호 : 2026.07.29.10:00 / {body} (*)",
    }


class TestParseSegments:
    def test_single_segment(self):
        assert parse_segments("[특보] 제07-100호 : ... / 폭염경보 변경 (*)") == [
            ("폭염경보", "변경")
        ]

    def test_compound_segments_split_on_middot(self):
        title = "[특보] 제07-92호 : ... / 폭염주의보 변경·폭염주의보 해제·열대야주의보 발표 (*)"
        assert parse_segments(title) == [("폭염주의보", "변경"), ("폭염주의보", "해제")]

    def test_ignores_non_heat_warnings(self):
        assert parse_segments("[특보] ... / 열대야주의보 발표 (*)") == []
        assert parse_segments("[특보] ... / 호우주의보 발표 (*)") == []

    def test_title_without_slash_body(self):
        assert parse_segments("잘못된 제목") == []


class TestCurrentWarnings:
    def test_issued_then_still_active(self):
        items = [warn(202607271000, "폭염주의보 발표", 96)]
        assert set(current_warnings(items)) == {"폭염주의보"}

    def test_release_clears_it(self):
        items = [
            warn(202607271000, "폭염주의보 발표", 96),
            warn(202607281600, "폭염주의보 해제", 99),
        ]
        assert current_warnings(items) == {}

    def test_reissue_after_release_is_active_again(self):
        items = [
            warn(202607271000, "폭염주의보 발표", 96),
            warn(202607271600, "폭염주의보 해제", 97),
            warn(202607281000, "폭염주의보 발표", 98),
        ]
        assert set(current_warnings(items)) == {"폭염주의보"}

    def test_out_of_order_input_is_replayed_chronologically(self):
        # API가 최신순으로 주므로 정렬이 깨져도 결과가 같아야 한다.
        items = [
            warn(202607281600, "폭염주의보 해제", 99),
            warn(202607271000, "폭염주의보 발표", 96),
        ]
        assert current_warnings(items) == {}

    def test_advisory_and_warning_tracked_separately(self):
        items = [
            warn(202607271000, "폭염주의보 발표", 96),
            warn(202607281000, "폭염경보 발표", 98),
            warn(202607281300, "폭염주의보 해제", 99),
        ]
        assert set(current_warnings(items)) == {"폭염경보"}

    def test_change_keeps_it_active(self):
        items = [
            warn(202607281000, "폭염경보 발표", 98),
            warn(202607291000, "폭염경보 변경", 100),
        ]
        assert set(current_warnings(items)) == {"폭염경보"}

    def test_keeps_first_issue_time_not_latest_change(self):
        items = [
            warn(202607281000, "폭염경보 발표", 98),
            warn(202607291000, "폭염경보 변경", 100),
        ]
        assert current_warnings(items)["폭염경보"] == datetime(2026, 7, 28, 10, 0)


class TestRecentReleases:
    def test_release_within_24h_is_reported(self):
        items = [
            warn(202607281000, "폭염주의보 발표", 98),
            warn(202607290800, "폭염주의보 해제", 99),
        ]
        assert set(recent_releases(items, NOW)) == {"폭염주의보"}

    def test_old_release_is_ignored(self):
        items = [
            warn(202607250800, "폭염주의보 발표", 93),
            warn(202607260800, "폭염주의보 해제", 94),
        ]
        assert recent_releases(items, NOW) == {}

    def test_release_then_reissue_is_not_reported(self):
        items = [
            warn(202607281000, "폭염주의보 발표", 98),
            warn(202607290600, "폭염주의보 해제", 99),
            warn(202607290800, "폭염주의보 발표", 100),
        ]
        assert recent_releases(items, NOW) == {}


class TestBuildEvents:
    def test_active_warning_becomes_event(self):
        items = [warn(202607291000, "폭염경보 발표", 100)]
        events = build_events(items, GANGNAM, NOW)
        assert len(events) == 1
        assert events[0].kind == "폭염경보"
        assert events[0].action == "발효 중"
        assert events[0].region == "서울 강남구"

    def test_no_warning_means_no_event(self):
        assert build_events([], GANGNAM, NOW) == []

    def test_key_includes_date_so_it_posts_once_per_day(self):
        items = [warn(202607281000, "폭염경보 발표", 98)]
        today = build_events(items, GANGNAM, datetime(2026, 7, 29, 9, 0))[0]
        tomorrow = build_events(items, GANGNAM, datetime(2026, 7, 30, 9, 0))[0]
        assert today.key != tomorrow.key
        assert today.key.startswith("20260729:")

    def test_same_day_rerun_produces_same_key(self):
        items = [warn(202607281000, "폭염경보 발표", 98)]
        a = build_events(items, GANGNAM, datetime(2026, 7, 29, 9, 0))[0]
        b = build_events(items, GANGNAM, datetime(2026, 7, 29, 14, 30))[0]
        assert a.key == b.key


def fcst(date, time, category, value):
    return {"fcstDate": date, "fcstTime": time, "category": category, "fcstValue": value}


class TestSummarizeTemps:
    def test_reads_daily_max_and_min(self):
        items = [
            fcst("20260729", "1500", "TMX", "36.0"),
            fcst("20260729", "0600", "TMN", "26.0"),
        ]
        assert summarize_temps(items, NOW) == {"today_max": 36.0, "today_min": 26.0}

    def test_ignores_other_days(self):
        assert summarize_temps([fcst("20260730", "1500", "TMX", "40.0")], NOW) == {}

    def test_tolerates_missing_values(self):
        assert summarize_temps([fcst("20260729", "1500", "TMP", "33")], NOW) == {}


class TestForecastLevels:
    def test_bands_are_ordered_by_temperature(self):
        names = [_forecast_level({"today_max": t})[0] for t in (36, 34, 31, 29, 22)]
        assert names == ["가마솥", "한여름", "더움", "살짝 더움", "선선"]

    def test_boundary_is_inclusive(self):
        assert _forecast_level({"today_max": 35.0})[0] == "가마솥"
        assert _forecast_level({"today_max": 34.9})[0] == "한여름"

    def test_missing_temperature_falls_back(self):
        assert _forecast_level({})[0] == "기온 미확인"

    def test_daily_key_is_once_per_day(self):
        a = forecast_event(GANGNAM, {}, datetime(2026, 7, 29, 9, 0))
        b = forecast_event(GANGNAM, {}, datetime(2026, 7, 29, 18, 0))
        c = forecast_event(GANGNAM, {}, datetime(2026, 7, 30, 9, 0))
        assert a.key == b.key != c.key


class TestState:
    def test_filter_new_removes_already_sent(self):
        events = build_events([warn(202607291000, "폭염경보 발표", 100)], GANGNAM, NOW)
        assert filter_new(events, mark(events, {})) == []

    def test_prune_drops_old_keys(self):
        sent = {"old": "2026-07-01T00:00:00", "new": "2026-07-29T00:00:00"}
        kept = prune(sent, NOW)
        assert "old" not in kept and "new" in kept


class TestCard:
    def test_active_warning_card_is_red_with_guide(self):
        event = build_events([warn(202607291000, "폭염경보 발표", 100)], GANGNAM, NOW)[0]
        attachment = build_attachment(event)
        assert attachment["color"] == "#D0021B"
        assert "이렇게 하세요" in attachment["text"]

    def test_release_card_is_green(self):
        items = [
            warn(202607281000, "폭염주의보 발표", 98),
            warn(202607290800, "폭염주의보 해제", 99),
        ]
        event = build_events(items, GANGNAM, NOW)[0]
        assert event.is_release
        assert build_attachment(event)["color"] == "#2FA84F"

    def test_forecast_card_has_playful_headline(self):
        event = forecast_event(GANGNAM, {"today_max": 34.0}, NOW)
        attachment = build_attachment(event)
        assert "한여름" in attachment["title"]
        assert "오늘도 덥습니다" in attachment["text"]
        assert attachment["color"] == "#F5A623"

    def test_forecast_card_omits_warning_field(self):
        event = forecast_event(GANGNAM, {"today_max": 31.0}, NOW)
        titles = [f["title"] for f in build_attachment(event)["fields"]]
        assert "특보" not in titles
        assert "낮 최고" in titles

    def test_forecast_card_survives_missing_temperature(self):
        attachment = build_attachment(forecast_event(GANGNAM, {}, NOW))
        assert "기온 미확인" in attachment["title"]
        assert attachment["text"]  # 빈 카드가 나가지 않는다

    def test_started_today_shows_badge(self):
        event = build_events([warn(202607290800, "폭염경보 발표", 100)], GANGNAM, NOW)[0]
        assert event.started_today
        assert "오늘 발효" in build_attachment(event)["title"]

    def test_continuing_warning_has_no_badge(self):
        event = build_events([warn(202607230800, "폭염경보 발표", 90)], GANGNAM, NOW)[0]
        assert not event.started_today
        assert "오늘 발효" not in build_attachment(event)["title"]

    def test_payload_bundles_all_events(self):
        items = [
            warn(202607291000, "폭염경보 발표", 100),
            warn(202607281000, "폭염주의보 발표", 97),
            warn(202607290800, "폭염주의보 해제", 99),
        ]
        payload = build_payload(build_events(items, GANGNAM, NOW), "봇", ":sunny:")
        assert len(payload["attachments"]) == 2  # 발효 중 1 + 해제 1
        assert payload["username"] == "봇"
