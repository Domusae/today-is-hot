"""시간대별 강수 정리. PTY/POP/SKY 원본만 쓰고 새 수치를 만들지 않는다."""
from src.precip import DayPart, max_pop, rain_pattern, summarize_dayparts


def day(**slots):
    """{"0900": {"PTY": "1", "POP": "80"}} 형태를 그대로 받는다."""
    return slots


def slot(pty="0", sky="1", pop="0"):
    return {"PTY": pty, "SKY": sky, "POP": pop}


class TestSummarizeDayparts:
    def test_splits_into_morning_afternoon_evening(self):
        parts = summarize_dayparts(
            day(**{"0900": slot(), "1400": slot(), "2000": slot()})
        )
        assert [p.name for p in parts] == ["오전", "오후", "저녁"]

    def test_skips_parts_without_data(self):
        parts = summarize_dayparts(day(**{"1400": slot()}))
        assert [p.name for p in parts] == ["오후"]

    def test_rain_in_a_part_is_detected(self):
        parts = summarize_dayparts(day(**{"0900": slot(pty="1", pop="80")}))
        assert parts[0].rain == "비"
        assert parts[0].pop == 80

    def test_shower_wins_over_plain_rain(self):
        # 소나기는 대비가 달라 대표값으로 올린다.
        parts = summarize_dayparts(
            day(**{"1300": slot(pty="1"), "1500": slot(pty="4")})
        )
        assert parts[0].rain == "소나기"

    def test_pop_is_the_max_within_the_part(self):
        parts = summarize_dayparts(
            day(**{"1300": slot(pop="20"), "1500": slot(pop="70")})
        )
        assert parts[0].pop == 70

    def test_sky_uses_the_most_common_value(self):
        parts = summarize_dayparts(
            day(**{"0700": slot(sky="4"), "0900": slot(sky="4"), "1100": slot(sky="1")})
        )
        assert parts[0].sky == "흐림"

    def test_label_prefers_rain_over_sky(self):
        parts = summarize_dayparts(day(**{"0900": slot(pty="1", sky="4")}))
        assert parts[0].label == "비"

    def test_label_falls_back_to_sky(self):
        parts = summarize_dayparts(day(**{"0900": slot(sky="3")}))
        assert parts[0].label == "구름많음"

    def test_snow_and_sleet_are_recognised(self):
        assert summarize_dayparts(day(**{"0900": slot(pty="3")}))[0].rain == "눈"
        assert summarize_dayparts(day(**{"0900": slot(pty="2")}))[0].rain == "비/눈"

    def test_empty_day(self):
        assert summarize_dayparts({}) == []

    def test_malformed_time_is_ignored(self):
        assert summarize_dayparts(day(**{"": slot(pty="1")})) == []


def parts(*specs):
    """("오전", "비", 80) 형태로 DayPart를 만든다."""
    return [DayPart(name=n, rain=r, sky="흐림", pop=p) for n, r, p in specs]


class TestRainPattern:
    def test_all_day_rain(self):
        assert rain_pattern(
            parts(("오전", "비", 80), ("오후", "비", 80), ("저녁", "비", 70))
        ) == "종일"

    def test_morning_only(self):
        assert rain_pattern(
            parts(("오전", "비", 80), ("오후", "", 10), ("저녁", "", 0))
        ) == "오전"

    def test_afternoon_and_evening(self):
        assert rain_pattern(
            parts(("오전", "", 0), ("오후", "비", 60), ("저녁", "비", 70))
        ) == "오후+저녁"

    def test_shower_takes_priority_over_timing(self):
        assert rain_pattern(
            parts(("오전", "", 0), ("오후", "소나기", 60), ("저녁", "", 0))
        ) == "소나기"

    def test_no_rain_but_high_chance(self):
        assert rain_pattern(parts(("오전", "", 70), ("오후", "", 30))) == "가능성"

    def test_no_rain_and_low_chance_is_silent(self):
        assert rain_pattern(parts(("오전", "", 10), ("오후", "", 20))) == ""

    def test_empty_is_silent(self):
        assert rain_pattern([]) == ""

    def test_single_part_raining_counts_as_all_day(self):
        # 자료가 저녁뿐인데 비가 오면, 아는 범위에선 종일이다.
        assert rain_pattern(parts(("저녁", "비", 80))) == "종일"


class TestMaxPop:
    def test_takes_the_highest(self):
        assert max_pop(parts(("오전", "", 30), ("오후", "비", 90))) == 90

    def test_empty_is_zero(self):
        assert max_pop([]) == 0
