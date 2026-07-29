from datetime import datetime

from src.card import _forecast_level, _pick, build_attachment, build_payload
from src.config import Region
from src.detector import build_events, forecast_event, summarize_temps
from src.state import filter_new, mark, prune

GANGNAM = Region(
    name="서울 강남구",
    stn_id="108",
    nx=61,
    ny=125,
    warn_area="서울",
    sub_area="서울동남권",
)
NOW = datetime(2026, 7, 29, 9, 0)

WARNING_T6 = "o 폭염경보 : 서울(서울서북권 제외), 대전"
ADVISORY_T6 = "o 폭염주의보 : 서울(서울서북권 제외), 대전"
CLEAR_T6 = "o 폭염경보 : 부산"


class TestBuildEvents:
    def test_active_warning_becomes_event(self):
        events = build_events(WARNING_T6, ADVISORY_T6, GANGNAM, 202607291000, NOW)
        assert [e.kind for e in events] == ["폭염경보", "폭염주의보"]
        assert events[0].action == "발효 중"
        assert events[1].is_release

    def test_no_warning_means_no_event(self):
        assert build_events(CLEAR_T6, CLEAR_T6, GANGNAM, None, NOW) == []

    def test_newly_issued_is_flagged(self):
        events = build_events(WARNING_T6, CLEAR_T6, GANGNAM, None, NOW)
        assert events[0].started_today

    def test_continuing_warning_is_not_flagged(self):
        events = build_events(WARNING_T6, WARNING_T6, GANGNAM, None, NOW)
        assert not events[0].started_today

    def test_without_previous_status_nothing_is_called_new(self):
        # 어제 통보문을 못 구했으면 신규인지 알 수 없다. 지어내지 않는다.
        events = build_events(WARNING_T6, None, GANGNAM, None, NOW)
        assert len(events) == 1
        assert not events[0].started_today

    def test_release_detected_against_yesterday(self):
        events = build_events(CLEAR_T6, WARNING_T6, GANGNAM, None, NOW)
        assert len(events) == 1
        assert events[0].is_release and events[0].kind == "폭염경보"

    def test_key_includes_date_so_it_posts_once_per_day(self):
        today = build_events(WARNING_T6, None, GANGNAM, None, datetime(2026, 7, 29, 9))[0]
        tomorrow = build_events(WARNING_T6, None, GANGNAM, None, datetime(2026, 7, 30, 9))[0]
        assert today.key != tomorrow.key
        assert today.key.startswith("20260729:")

    def test_same_day_rerun_produces_same_key(self):
        a = build_events(WARNING_T6, None, GANGNAM, None, datetime(2026, 7, 29, 9))[0]
        b = build_events(WARNING_T6, None, GANGNAM, None, datetime(2026, 7, 29, 14))[0]
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

    def test_falls_back_to_hourly_when_tmx_is_gone(self):
        # 오후 실행 시 오늘의 TMX가 예보에서 빠지는 경우
        items = [
            fcst("20260729", "1500", "TMP", "34"),
            fcst("20260729", "1800", "TMP", "31"),
        ]
        assert summarize_temps(items, NOW) == {"today_max": 34.0, "today_min": 31.0}

    def test_prefers_tmx_over_hourly_fallback(self):
        items = [
            fcst("20260729", "1500", "TMX", "36.0"),
            fcst("20260729", "1500", "TMP", "34"),
        ]
        assert summarize_temps(items, NOW)["today_max"] == 36.0

    def test_ignores_other_days(self):
        assert summarize_temps([fcst("20260730", "1500", "TMX", "40.0")], NOW) == {}

    def test_empty_input(self):
        assert summarize_temps([], NOW) == {}


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


class TestRotatingMessages:
    def test_same_day_gives_same_message(self):
        pool = ["a", "b", "c"]
        assert _pick(pool, datetime(2026, 7, 29, 9)) == _pick(pool, datetime(2026, 7, 29, 20))

    def test_message_changes_the_next_day(self):
        pool = ["a", "b", "c"]
        assert _pick(pool, datetime(2026, 7, 29)) != _pick(pool, datetime(2026, 7, 30))

    def test_cycles_through_the_whole_pool(self):
        pool = ["a", "b", "c"]
        picked = {_pick(pool, datetime(2026, 7, 29 + i)) for i in range(3)}
        assert picked == set(pool)

    def test_empty_pool_is_safe(self):
        assert _pick([], NOW) == ""

    def test_forecast_card_text_rotates_by_day(self):
        event = forecast_event(GANGNAM, {"today_max": 34.0}, NOW)
        day1 = build_attachment(event, datetime(2026, 7, 29))["text"]
        day2 = build_attachment(event, datetime(2026, 7, 30))["text"]
        assert day1 != day2

    def test_warning_card_text_rotates_by_day(self):
        event = build_events(WARNING_T6, None, GANGNAM, None, NOW)[0]
        day1 = build_attachment(event, datetime(2026, 7, 29))["text"]
        day2 = build_attachment(event, datetime(2026, 7, 30))["text"]
        assert day1 != day2


class TestState:
    def test_filter_new_removes_already_sent(self):
        events = build_events(WARNING_T6, None, GANGNAM, None, NOW)
        assert filter_new(events, mark(events, {})) == []

    def test_prune_drops_old_keys(self):
        sent = {"old": "2026-07-01T00:00:00", "new": "2026-07-29T00:00:00"}
        kept = prune(sent, NOW)
        assert "old" not in kept and "new" in kept


class TestCard:
    def test_severe_warning_is_darkest(self):
        event = build_events("o 폭염중대경보 : 서울", None, GANGNAM, None, NOW)[0]
        attachment = build_attachment(event, NOW)
        assert attachment["color"] == "#8B0000"
        assert "🚨" in attachment["title"]
        assert "멈추기" in attachment["text"]

    def test_active_warning_card_is_red_with_guide(self):
        event = build_events(WARNING_T6, None, GANGNAM, None, NOW)[0]
        attachment = build_attachment(event, NOW)
        assert attachment["color"] == "#D0021B"
        assert "이렇게 해요" in attachment["text"]

    def test_release_card_is_green(self):
        event = build_events(CLEAR_T6, WARNING_T6, GANGNAM, None, NOW)[0]
        assert build_attachment(event, NOW)["color"] == "#2FA84F"

    def test_forecast_card_has_playful_headline(self):
        event = forecast_event(GANGNAM, {"today_max": 34.0}, NOW)
        attachment = build_attachment(event, NOW)
        assert "한여름" in attachment["title"]
        assert attachment["color"] == "#F5A623"

    def test_only_temperature_fields_remain(self):
        event = forecast_event(GANGNAM, {"today_max": 31.0, "today_min": 24.0}, NOW)
        titles = [f["title"] for f in build_attachment(event, NOW)["fields"]]
        assert titles == ["낮 최고", "아침 최저"]

    def test_forecast_card_survives_missing_temperature(self):
        attachment = build_attachment(forecast_event(GANGNAM, {}, NOW), NOW)
        assert "기온 미확인" in attachment["title"]
        assert attachment["text"]

    def test_started_today_shows_badge(self):
        event = build_events(WARNING_T6, CLEAR_T6, GANGNAM, None, NOW)[0]
        assert "방금 떴어요" in build_attachment(event, NOW)["title"]

    def test_region_is_never_displayed(self):
        # 읽는 사람이 정해져 있으므로 지역은 카드에 나오지 않는다.
        for event in (
            build_events(WARNING_T6, None, GANGNAM, None, NOW)[0],
            build_events(CLEAR_T6, WARNING_T6, GANGNAM, None, NOW)[0],
            forecast_event(GANGNAM, {"today_max": 31.0}, NOW),
        ):
            attachment = build_attachment(event, NOW)
            rendered = attachment["title"] + attachment["text"] + str(attachment["fields"])
            assert "강남" not in rendered and "서울" not in rendered

    def test_region_still_scopes_the_dedup_key(self):
        # 표시만 빼는 것이고, 중복 방지 키에는 지역이 남아야 한다.
        event = build_events(WARNING_T6, None, GANGNAM, None, NOW)[0]
        assert "서울 강남구" in event.key

    def test_payload_bundles_all_events(self):
        events = build_events(WARNING_T6, ADVISORY_T6, GANGNAM, None, NOW)
        payload = build_payload(events, "봇", ":sunny:", NOW)
        assert len(payload["attachments"]) == 2
        assert payload["username"] == "봇"
