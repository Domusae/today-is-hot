"""오늘 강수 예보 판정. PTY/POP 원본만 쓰고 새 수치를 만들지 않는다."""
from src.precip import rain_outlook


def slot(pty="0", pop="0"):
    return {"PTY": pty, "POP": pop}


class TestRainOutlook:
    def test_no_rain_returns_none(self):
        assert rain_outlook({"0900": slot(), "1500": slot(pop="20")}) is None

    def test_high_chance_without_pty_is_still_no_rain(self):
        # 강수형태가 없으면 비 예보가 아니다. 확률만으로 비가 온다고 말하지 않는다.
        assert rain_outlook({"1500": slot(pop="60")}) is None

    def test_detects_rain(self):
        outlook = rain_outlook({"1500": slot(pty="1", pop="80")})
        assert outlook.kind == "비"
        assert outlook.pop == 80

    def test_shower_wins_over_plain_rain(self):
        outlook = rain_outlook({"1300": slot(pty="1"), "1500": slot(pty="4")})
        assert outlook.kind == "소나기"

    def test_snow_and_sleet(self):
        assert rain_outlook({"0900": slot(pty="3")}).kind == "눈"
        assert rain_outlook({"0900": slot(pty="2")}).kind == "비/눈"

    def test_pop_is_the_daily_max(self):
        outlook = rain_outlook({"0900": slot(pty="1", pop="30"), "1500": slot(pop="90")})
        assert outlook.pop == 90

    def test_empty_day(self):
        assert rain_outlook({}) is None

    def test_unknown_pty_code_is_ignored(self):
        assert rain_outlook({"0900": slot(pty="9")}) is None

    def test_missing_pop_defaults_to_zero(self):
        assert rain_outlook({"0900": {"PTY": "1"}}).pop == 0
